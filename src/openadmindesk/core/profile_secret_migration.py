"""Explicit migration of legacy plaintext profile secrets into the vault."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from openadmindesk.core.account import Account
from openadmindesk.core.vault_manager import VaultManager

SECRET_COLUMNS = ("password", "private_key_passphrase", "rdp_gateway_password")


@dataclass(frozen=True)
class ProfileSecretScan:
    name: str
    has_password: bool
    has_passphrase: bool
    has_gateway_password: bool
    has_credential_id: bool
    has_gateway_credential_id: bool


@dataclass(frozen=True)
class ProfileSecretScanReport:
    total_profiles: int
    affected_profiles: int
    primary_only: int
    gateway_only: int
    mixed: int
    profiles: tuple[ProfileSecretScan, ...]


@dataclass(frozen=True)
class ProfileSecretMigrationResult:
    """Result of a profile secret migration operation.

    Attributes:
        scanned: Number of profiles with legacy secrets that were processed.
        primary_migrated: Count of primary secrets (password/passphrase) moved
            into new vault accounts.
        gateway_migrated: Count of gateway secrets (rdp_gateway_password) moved
            into new vault accounts.
        primary_cleared: Count of primary secrets cleared from the DB because
            matching vault accounts already existed.
        gateway_cleared: Count of gateway secrets cleared from the DB because
            matching vault accounts already existed.
        backup: Result of the pre-migration backup, or None if no rows needed
            migration.
    """

    scanned: int = 0
    primary_migrated: int = 0
    gateway_migrated: int = 0
    primary_cleared: int = 0
    gateway_cleared: int = 0
    backup: Optional["ProfileSecretBackupResult"] = None

    @property
    def migrated(self) -> int:
        """Total vault account operations (compatibility with legacy callers)."""
        return self.primary_migrated + self.gateway_migrated

    @property
    def cleared_only(self) -> int:
        """Total clearing operations (compatibility with legacy callers)."""
        return self.primary_cleared + self.gateway_cleared


def scan_plaintext_profile_secrets(db_path: str) -> ProfileSecretScanReport:
    """Scan profiles for plaintext secrets without modifying anything.

    Returns a read-only report with metadata about which profiles contain
    plaintext secrets. Never opens the vault or writes to the database.
    """
    profiles_data = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT name, password, private_key_passphrase,
                   rdp_gateway_password, credential_id, rdp_gateway_credential_id
            FROM profiles
            ORDER BY name
            """
        ).fetchall()

        primary_only = gateway_only = mixed = 0

        for row in rows:
            has_password = bool(row["password"])
            has_passphrase = bool(row["private_key_passphrase"])
            has_gateway_password = bool(row["rdp_gateway_password"])
            has_credential_id = bool(row["credential_id"])
            has_gateway_credential_id = bool(row["rdp_gateway_credential_id"])

            scan = ProfileSecretScan(
                name=row["name"],
                has_password=has_password,
                has_passphrase=has_passphrase,
                has_gateway_password=has_gateway_password,
                has_credential_id=has_credential_id,
                has_gateway_credential_id=has_gateway_credential_id,
            )
            profiles_data.append(scan)

            if has_password or has_passphrase:
                if has_gateway_password:
                    mixed += 1
                else:
                    primary_only += 1
            elif has_gateway_password:
                gateway_only += 1

    return ProfileSecretScanReport(
        total_profiles=len(profiles_data),
        affected_profiles=primary_only + gateway_only + mixed,
        primary_only=primary_only,
        gateway_only=gateway_only,
        mixed=mixed,
        profiles=tuple(profiles_data),
    )


# ── Private helpers for Phase 9.6c migration ────────────────────────────────


def _query_legacy_rows(db_path: str) -> list[sqlite3.Row]:
    """Return all profile rows that contain at least one non-empty plaintext
    secret, ordered by name for deterministic processing."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT name, host, port, username,
                   password, private_key_passphrase, rdp_gateway_password,
                   credential_id, rdp_gateway_credential_id,
                   rdp_gateway, rdp_gateway_username
            FROM profiles
            WHERE (password IS NOT NULL AND password != '')
               OR (private_key_passphrase IS NOT NULL AND private_key_passphrase != '')
               OR (rdp_gateway_password IS NOT NULL AND rdp_gateway_password != '')
            ORDER BY name
            """
        ).fetchall()


def _resolve_primary_account(
    vault: VaultManager,
    row: sqlite3.Row,
    compensation_stack: list,
) -> tuple[Optional[str], int, int]:
    """Resolve primary vault account for a legacy profile row.

    If a vault account already exists with a matching credential_id and
    matching secret values, the existing account is retained (no upsert).
    If values differ, a RuntimeError is raised before any vault write.
    If no vault account exists, a new Account is created with the
    profile's credential_id (or a generated one) and added to the vault.

    Returns:
        Tuple of (credential_id, migrate_increment, clear_increment).

    Raises:
        RuntimeError: On vault conflict (existing account has different values)
            or vault write failure. Message contains no secret values.
    """
    name = row["name"]
    password = row["password"]
    passphrase = row["private_key_passphrase"]
    credential_id = row["credential_id"]

    has_password = bool(password)
    has_passphrase = bool(passphrase)

    if not has_password and not has_passphrase:
        return credential_id, 0, 0

    if credential_id:
        existing = vault.get_account(credential_id)
        if existing is not None:
            secrets_match = True
            if has_password and existing.password != password:
                secrets_match = False
            if has_passphrase and existing.private_key_passphrase != passphrase:
                secrets_match = False
            if not secrets_match:
                raise RuntimeError(
                    f"Vault account '{credential_id}' for profile '{name}' "
                    "has different secret values than the profile. "
                    "Resolve the conflict manually before migration."
                )
            # Existing account matches — no vault write needed
            return credential_id, 0, 1

    # Create a new vault account (use existing credential_id if set but missing)
    new_id: Optional[str] = credential_id if credential_id else None
    acct = Account(
        id=new_id,
        name=name,
        username=row["username"] or "",
        host=row["host"] or "",
        port=row["port"] or 22,
        service_type="ssh",
        password=password if has_password else None,
        private_key_passphrase=passphrase if has_passphrase else None,
    )
    if not vault.add_account(acct):
        raise RuntimeError(
            f"Failed to add primary vault account for profile '{name}'"
        )
    compensation_stack.append(acct.id)
    return acct.id, 1, 0


def _resolve_gateway_account(
    vault: VaultManager,
    row: sqlite3.Row,
    compensation_stack: list,
) -> tuple[Optional[str], int, int]:
    """Resolve RDP gateway vault account for a legacy profile row.

    If a vault account already exists with a matching
    rdp_gateway_credential_id and matching password, the existing account
    is retained (no upsert).  If values differ, a RuntimeError is raised
    before any vault write.  If no vault account exists, a new Account
    with ``service_type`` ``rdp-gateway`` is created.

    Returns:
        Tuple of (rdp_gateway_credential_id, migrate_increment,
        clear_increment).

    Raises:
        RuntimeError: On vault conflict or vault write failure.
    """
    name = row["name"]
    gateway_password = row["rdp_gateway_password"]
    gateway_credential_id = row["rdp_gateway_credential_id"]
    gateway_host = row["rdp_gateway"]
    gateway_username = row["rdp_gateway_username"]

    if not gateway_password:
        return gateway_credential_id, 0, 0

    if gateway_credential_id:
        existing = vault.get_account(gateway_credential_id)
        if existing is not None:
            if existing.password != gateway_password:
                raise RuntimeError(
                    f"Vault gateway account '{gateway_credential_id}' for "
                    f"profile '{name}' has a different password than the "
                    "profile's gateway. Resolve the conflict manually "
                    "before migration."
                )
            # Existing account matches — no vault write needed
            return gateway_credential_id, 0, 1

    # Create a new gateway vault account
    new_id: Optional[str] = gateway_credential_id if gateway_credential_id else None
    acct = Account(
        id=new_id,
        name=f"{name}-gateway",
        username=gateway_username or "",
        host=gateway_host or "",
        service_type="rdp-gateway",
        password=gateway_password,
    )
    if not vault.add_account(acct):
        raise RuntimeError(
            f"Failed to add gateway vault account for profile '{name}'"
        )
    compensation_stack.append(acct.id)
    return acct.id, 1, 0


# ── Phase 9.6c: Compensated primary+gateway migration ──────────────────────


def migrate_plaintext_profile_secrets(
    db_path: str,
    vault: VaultManager,
    *,
    confirm_cleartext_removal: bool = False,
    backup_dir: Optional[str] = None,
) -> ProfileSecretMigrationResult:
    """Move legacy profile secrets to vault accounts and clear profile columns.

    This is intentionally explicit and never runs during normal application
    startup.

    The migration is fully compensated:
      1. Backs up the database and encrypted vault before any mutation.
      2. For each affected row, checks vault conflicts and either creates
         new vault accounts or retains matching existing ones.
      3. Updates all affected rows in a single SQLite transaction, setting
         credential IDs and clearing all three plaintext secret columns.
      4. On any failure the DB transaction is rolled back and vault accounts
         created during this call are removed.  If compensation fails, the
         resulting RuntimeError includes backup paths but never secret values.

    Args:
        db_path: Path to the SQLite profile database.
        vault: An unlocked VaultManager instance.
        confirm_cleartext_removal: Must be ``True`` to proceed.
        backup_dir: Target backup directory (passed to
            :func:`create_profile_secret_backups`).

    Returns:
        ProfileSecretMigrationResult with counts of migrated / cleared
        secrets and the backup result.

    Raises:
        RuntimeError: If preconditions are not met, a vault conflict exists,
            vault or DB writes fail, or compensation fails after a failure.
    """
    if not confirm_cleartext_removal:
        raise RuntimeError(
            "Migration requires confirm_cleartext_removal=True"
        )

    if not vault.is_unlocked():
        raise RuntimeError("Vault must be unlocked for migration")

    # 1) Query affected rows
    rows = _query_legacy_rows(db_path)
    scanned = len(rows)

    if scanned == 0:
        return ProfileSecretMigrationResult(scanned=0, backup=None)

    # 2) Back up before any mutation
    backup = create_profile_secret_backups(
        db_path, vault.vault_path, backup_dir
    )

    # 3) Process each row — resolve vault accounts, build compensation stack
    compensation_stack: list[str] = []
    db_updates: list[dict[str, object]] = []
    primary_migrated = 0
    gateway_migrated = 0
    primary_cleared = 0
    gateway_cleared = 0

    try:
        for row in rows:
            # Refresh activity time and detect auto-lock before each row
            if not vault.is_unlocked():
                raise RuntimeError(
                    "Vault became locked during migration; "
                    "re-unlock and retry"
                )

            cred_id, prim_mig, prim_clr = _resolve_primary_account(
                vault, row, compensation_stack,
            )
            primary_migrated += prim_mig
            primary_cleared += prim_clr

            gw_cred_id, gw_mig, gw_clr = _resolve_gateway_account(
                vault, row, compensation_stack,
            )
            gateway_migrated += gw_mig
            gateway_cleared += gw_clr

            if prim_mig == 0 and gw_mig == 0 and prim_clr == 0 and gw_clr == 0:
                continue  # no changes for this row

            db_updates.append({
                "name": row["name"],
                "credential_id": cred_id,
                "rdp_gateway_credential_id": gw_cred_id,
            })

        # 4) Single DB transaction — update all rows atomically
        with sqlite3.connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for update in db_updates:
                    conn.execute(
                        """UPDATE profiles
                           SET credential_id = ?,
                               rdp_gateway_credential_id = ?,
                               password = NULL,
                               private_key_passphrase = NULL,
                               rdp_gateway_password = NULL
                           WHERE name = ?""",
                        (
                            update["credential_id"],
                            update["rdp_gateway_credential_id"],
                            update["name"],
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return ProfileSecretMigrationResult(
            scanned=scanned,
            primary_migrated=primary_migrated,
            gateway_migrated=gateway_migrated,
            primary_cleared=primary_cleared,
            gateway_cleared=gateway_cleared,
            backup=backup,
        )

    except Exception as exc:
        # 5) Compensation: remove vault accounts created during this call
        compensation_errors: list[str] = []
        for acct_id in compensation_stack:
            try:
                removed = vault.remove_account(acct_id)
                if not removed:
                    # remove_account returned False — diagnose why
                    if not vault.is_unlocked():
                        compensation_errors.append(
                            f"Vault locked while compensating account '{acct_id}'"
                        )
                    else:
                        still_exists = vault.get_account(acct_id)
                        if still_exists is not None:
                            compensation_errors.append(
                                f"Failed to remove account '{acct_id}'"
                            )
                        # else: already absent — acceptable
            except Exception as ce:
                compensation_errors.append(
                    f"Error compensating account '{acct_id}': {ce}"
                )

        if compensation_errors:
            raise RuntimeError(
                f"Migration failed and vault compensation had errors. "
                f"Backup paths: DB={backup.db_backup_path}, "
                f"Vault={backup.vault_backup_path}. "
                f"Compensation errors: {'; '.join(compensation_errors)}"
            ) from exc

        # Re-raise original exception (compensation succeeded)
        raise


# ── Phase 9.6b: Secure SQLite+vault backup primitives ────────────────────────


@dataclass(frozen=True)
class ProfileSecretBackupResult:
    """Result of a profile secret backup operation.

    Attributes:
        db_backup_path: Absolute path to the SQLite backup file.
        vault_backup_path: Absolute path to the encrypted vault backup file.
        db_sha256: SHA-256 hex digest of the database backup.
        vault_sha256: SHA-256 hex digest of the vault backup.
    """

    db_backup_path: str
    vault_backup_path: str
    db_sha256: str
    vault_sha256: str


def _compute_file_sha256(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file using buffered reads."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def create_profile_secret_backups(
    db_path: str,
    vault_path: str,
    backup_dir: Optional[str] = None,
) -> ProfileSecretBackupResult:
    """Create secure backups of the profile database and encrypted vault.

    The backup process:
    1. Validates source files exist as regular files (no decryption).
    2. Creates or reuses the backup directory (mode 0700 for new dirs).
    3. Creates unique temp files via ``tempfile.mkstemp`` with a shared
       UTC timestamp prefix (mode 0600, no symlink following).
    4. Performs a SQLite ``backup()`` via a read-only source connection;
       verifies ``PRAGMA integrity_check`` on the destination.
    5. Copies the encrypted vault as raw binary in buffered chunks,
       with ``flush`` + ``fsync``.
    6. Computes SHA-256 hashes of the resulting files; confirms vault
       backup matches source (DB backup content may differ due to
       SQLite journaling).
    7. On any exception, removes all files created by this call and
       raises ``RuntimeError``.

    Args:
        db_path: Path to the SQLite profile database.
        vault_path: Path to the encrypted vault JSON file.
        backup_dir: Target backup directory. Defaults to ``<db_parent>/backups``.

    Returns:
        ProfileSecretBackupResult with paths and SHA-256 hex digests.

    Raises:
        RuntimeError: On any failure (source missing, I/O, integrity).
            The error message contains no secret content.
    """
    created_files: list[str] = []

    try:
        # 1) Validate source files — reject symlinks before isfile
        if os.path.islink(db_path):
            raise RuntimeError(
                f"Source database is a symbolic link: {os.path.abspath(db_path)}"
            )
        if os.path.islink(vault_path):
            raise RuntimeError(
                f"Source vault is a symbolic link: {os.path.abspath(vault_path)}"
            )

        if not os.path.isfile(db_path):
            raise RuntimeError(
                f"Source database is not a regular file: {os.path.abspath(db_path)}"
            )
        if not os.path.isfile(vault_path):
            raise RuntimeError(
                f"Source vault is not a regular file: {os.path.abspath(vault_path)}"
            )

        abs_db = str(Path(db_path).resolve())
        abs_vault = str(Path(vault_path).resolve())

        # 2) Determine and prepare backup directory (mode 0700 for new dirs)
        if backup_dir is None:
            backup_dir = str(Path(abs_db).parent / "backups")
        os.makedirs(backup_dir, mode=0o700, exist_ok=True)

        # 3) Shared UTC timestamp for unique file names
        utc_now = datetime.now(timezone.utc)
        timestamp = utc_now.strftime("%Y%m%dT%H%M%SZ")

        # 4) SQLite backup via read-only URI + Connection.backup()
        fd_db, db_backup_path = tempfile.mkstemp(
            prefix=f"profiles_backup_{timestamp}_",
            suffix=".db",
            dir=backup_dir,
        )
        os.close(fd_db)
        created_files.append(db_backup_path)

        db_uri = f"{Path(abs_db).resolve().as_uri()}?mode=ro"
        source_conn = sqlite3.connect(db_uri, uri=True)
        try:
            dest_conn = sqlite3.connect(db_backup_path)
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            source_conn.close()

        # Verify destination integrity
        check_conn = sqlite3.connect(db_backup_path)
        try:
            row = check_conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()
            if row is None or row[0] != "ok":
                raise RuntimeError(
                    f"Database backup integrity check failed: {row}"
                )
        finally:
            check_conn.close()

        os.chmod(db_backup_path, 0o600)

        # 5) Vault binary copy using existing mkstemp fd
        fd_vault, vault_backup_path = tempfile.mkstemp(
            prefix=f"vault_backup_{timestamp}_",
            suffix=".json",
            dir=backup_dir,
        )
        created_files.append(vault_backup_path)

        with open(abs_vault, "rb") as src:
            with os.fdopen(fd_vault, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())

        os.chmod(vault_backup_path, 0o600)

        # 6) Compute SHA-256 hashes
        db_sha256 = _compute_file_sha256(db_backup_path)
        vault_sha256 = _compute_file_sha256(vault_backup_path)

        # Verify vault source/backup are identical
        vault_src_sha256 = _compute_file_sha256(abs_vault)
        if vault_src_sha256 != vault_sha256:
            raise RuntimeError(
                "Vault backup SHA-256 does not match source"
            )

        return ProfileSecretBackupResult(
            db_backup_path=db_backup_path,
            vault_backup_path=vault_backup_path,
            db_sha256=db_sha256,
            vault_sha256=vault_sha256,
        )

    except Exception as e:
        # Clean up all files created by this call; do not touch pre-existing files
        for f in created_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:  # keep cleaning on failure path
                pass
        raise RuntimeError(
            f"Profile secret backup failed: {e}"
        ) from e
