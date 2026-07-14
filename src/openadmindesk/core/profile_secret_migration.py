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
    scanned: int = 0
    migrated: int = 0
    cleared_only: int = 0


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


def migrate_plaintext_profile_secrets(
    db_path: str,
    vault: VaultManager,
    *,
    confirm_cleartext_removal: bool = False,
) -> ProfileSecretMigrationResult:
    """Move legacy profile secrets to vault accounts and clear profile columns.

    This is intentionally explicit and never runs during normal application startup.
    """
    # Fail closed: live migration is disabled pending safe compensated migration
    raise RuntimeError(
        "live migration is disabled pending safe compensated migration; "
        "use --dry-run for assessment"
    )


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
