"""Vault upgrade orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from contextlib import suppress
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

from openadmindesk.core.account import Account
from openadmindesk.core.vault_format import VaultFormat, detect_version
from openadmindesk.core.vault_manager import VaultManager


@dataclass(frozen=True)
class VaultUpgradeResult:
    """Result of a vault upgrade operation."""

    source_version: int
    target_version: int
    accounts_reencrypted: int
    source_sha256: str
    target_sha256: str
    backup_deleted: bool
    retained_backup_path: Optional[str] = None


class VaultUpgradeError(RuntimeError):
    """Raised when a vault upgrade operation fails."""

    def __init__(
        self,
        message: str,
        *,
        rollback_succeeded: Optional[bool] = None,
        recovery_backup_path: Optional[str] = None,
        source_sha256: Optional[str] = None,
        backup_sha256: Optional[str] = None,
    ) -> None:
        """Initialise the error with optional recovery metadata.

        Args:
            message: Human-readable error description.
            rollback_succeeded: Whether an automatic rollback completed.
            recovery_backup_path: Path to a backup that can be used for
                manual recovery.
            source_sha256: SHA-256 hex digest of the source vault before
                the upgrade was attempted.
            backup_sha256: SHA-256 hex digest of the backup file.
        """
        super().__init__(message)
        self.rollback_succeeded = rollback_succeeded
        self.recovery_backup_path = recovery_backup_path
        self.source_sha256 = source_sha256
        self.backup_sha256 = backup_sha256


_ACCOUNT_FIELDS = frozenset(field.name for field in fields(Account))


@dataclass(frozen=True)
class _BackupInfo:
    """Metadata about a created vault backup file."""

    path: Path
    sha256: str


def _sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    This helper assumes a preflight caller; normal exceptions can propagate
    internally.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_source_document(path: Path) -> dict[str, object]:
    """Load and validate a version-1 vault document from disk.

    Args:
        path: Filesystem path to the vault file.

    Returns:
        The parsed vault document as a dictionary.

    Raises:
        VaultUpgradeError: If the path is inaccessible, is not a regular
            file, contains invalid JSON, is not a dict, is already or
            unsupported version, or fails format validation.
    """
    # Reject missing, inaccessible, non-regular paths (prevents FIFO block).
    try:
        st = path.lstat()
    except OSError:
        raise VaultUpgradeError("Vault source is unavailable") from None

    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise VaultUpgradeError("Vault source is not a regular file")

    # Read and parse JSON.
    try:
        text = path.read_text(encoding="utf-8")
        document: dict[str, object] = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VaultUpgradeError("Vault source is not valid JSON") from None

    if not isinstance(document, dict):
        raise VaultUpgradeError("Vault source is not a valid JSON object")

    # Version check.
    version = detect_version(document)
    if version == 2:
        raise VaultUpgradeError("Vault source is already version 2")
    if version != 1:
        raise VaultUpgradeError("Vault source version is unsupported")

    # Schema validation.
    if not VaultFormat.validate_vault_format(document):
        raise VaultUpgradeError("Vault source format is invalid")

    return document


def _validate_raw_accounts(document: dict[str, object]) -> tuple[str, ...]:
    """Validate raw account entries in a v1 vault document.

    Checks that ``accounts`` is a list of dicts, that each dict contains
    only known keys (matching ``Account`` fields), and that every entry
    has a non-empty ``id`` with no duplicates.

    Args:
        document: A loaded and format-validated v1 vault dictionary.

    Returns:
        Tuple of account IDs in source order.

    Raises:
        VaultUpgradeError: If validation fails.
    """
    accounts = document.get("accounts")
    if not isinstance(accounts, list):
        raise VaultUpgradeError("Vault accounts is not a list")

    ids: list[str] = []
    ids_seen: set[str] = set()

    for i, entry in enumerate(accounts):
        if not isinstance(entry, dict):
            raise VaultUpgradeError(
                f"Vault account entry at index {i} is not a dict"
            )

        # Reject unknown keys before any Account construction.
        unknown = set(entry.keys()) - _ACCOUNT_FIELDS
        if unknown:
            raise VaultUpgradeError(
                f"Vault account entry at index {i} has unknown keys"
            )

        # Require id is a non-empty string (whitespace-only rejected).
        # Preserve the original value; do not trim.
        acct_id = entry.get("id")
        if not isinstance(acct_id, str) or not acct_id.strip():
            raise VaultUpgradeError(
                f"Vault account entry at index {i} has an invalid id"
            )

        if acct_id in ids_seen:
            raise VaultUpgradeError("Duplicate vault account id detected")

        ids_seen.add(acct_id)
        ids.append(acct_id)

    return tuple(ids)


def _create_secure_backup(path: Path) -> _BackupInfo:
    """Create a secure owner-only backup of a vault file in the same
    directory.

    This helper assumes the caller has performed preflight validation
    confirming *path* exists, is accessible, and is a regular file.
    The source file is never modified.

    Args:
        path: Filesystem path to the source vault file.

    Returns:
        ``_BackupInfo`` containing the backup path and its SHA-256 hex
        digest.

    Raises:
        VaultUpgradeError: If any step of backup creation fails.
    """
    fd: int = -1
    backup_path: Path | None = None
    try:
        # Compute source hash before touching the filesystem.
        source_hash = _sha256_file(path)

        # Create a unique hidden temporary file in the same parent
        # directory as the source.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.v1-backup-",
            suffix=".tmp",
            dir=str(path.parent),
        )
        backup_path = Path(tmp_name)

        # Restrict permissions to owner read/write (0600).
        os.chmod(backup_path, 0o600)

        # Stream source bytes into the backup file.
        with os.fdopen(fd, "wb") as f:
            fd = -1  # fd is now owned by the file object
            with path.open("rb") as src:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            f.flush()
            os.fsync(f.fileno())

        # Verify backup integrity against the source.
        backup_hash = _sha256_file(backup_path)
        if backup_hash != source_hash:
            raise VaultUpgradeError(
                "Vault backup integrity check failed"
            )

        return _BackupInfo(backup_path, backup_hash)

    except VaultUpgradeError:
        # Clean up temporary file, then re-raise unchanged.
        # Each cleanup step is best-effort; exceptions must never
        # replace the original VaultUpgradeError.
        if fd >= 0:
            with suppress(Exception):
                os.close(fd)
        if backup_path is not None:
            with suppress(Exception):
                backup_path.unlink(missing_ok=True)
        raise

    except Exception:
        # Clean up temporary file.
        # Each cleanup step is best-effort; exceptions must never
        # replace the original translated VaultUpgradeError.
        if fd >= 0:
            with suppress(Exception):
                os.close(fd)
        if backup_path is not None:
            with suppress(Exception):
                backup_path.unlink(missing_ok=True)
        raise VaultUpgradeError(
            "Vault backup creation failed"
        ) from None


def _snapshot_v1_accounts(
    path: Path,
    master_password: str,
    expected_ids: tuple[str, ...],
) -> tuple[Account, ...]:
    """Decrypt and verify all accounts from a version-1 vault.

    Args:
        path: Filesystem path to the vault file.
        master_password: The master password to unlock the vault.
        expected_ids: The exact ordered tuple of account IDs expected.

    Returns:
        A tuple of decrypted ``Account`` objects matching the expected
        IDs.

    Raises:
        VaultUpgradeError: If the vault cannot be unlocked or the
            decrypted accounts cannot be verified.
    """
    manager: VaultManager | None = None
    accounts: tuple[Account, ...] = ()
    try:
        manager = VaultManager(str(path))
        if not manager.unlock(master_password):
            raise VaultUpgradeError(
                "Vault source password is invalid or data is unreadable"
            )

        accounts = tuple(manager.get_all_accounts())

        # Verify every returned object is an Account with a non-empty
        # string id.
        for acct in accounts:
            if not isinstance(acct, Account):
                raise VaultUpgradeError(
                    "Vault source accounts could not be verified"
                )
            if not isinstance(acct.id, str) or not acct.id:
                raise VaultUpgradeError(
                    "Vault source accounts could not be verified"
                )

        # Verify the ordered list of IDs matches exactly.
        actual_ids = tuple(acct.id for acct in accounts)
        if actual_ids != expected_ids:
            raise VaultUpgradeError(
                "Vault source accounts could not be verified"
            )

        return accounts

    except VaultUpgradeError:
        raise

    except Exception:
        raise VaultUpgradeError(
            "Vault source accounts could not be verified"
        ) from None

    finally:
        if manager is not None:
            manager.lock()
            manager.close()


def _account_map(
    expected_ids: tuple[str, ...],
    accounts: tuple[Account, ...],
) -> dict[str, Account]:
    """Validate accounts and build an ID-to-Account mapping.

    Every entry in *accounts* must be an ``Account`` instance with a
    non-empty string id.  IDs must be unique.  The ordered list of IDs
    extracted from *accounts* must equal *expected_ids*.

    Args:
        expected_ids: The exact tuple of account IDs expected, in order.
        accounts: Account objects to validate and index.

    Returns:
        A dictionary mapping each account ID to its ``Account`` object.

    Raises:
        VaultUpgradeError: If any validation check fails.  Error messages
            do not contain account fields or secrets.
    """
    if len(expected_ids) != len(accounts):
        raise VaultUpgradeError(
            "Account count mismatch during vault upgrade"
        )

    seen: set[str] = set()
    result: dict[str, Account] = {}

    for acct in accounts:
        if not isinstance(acct, Account):
            raise VaultUpgradeError(
                "Invalid account entry encountered during vault upgrade"
            )

        acct_id = acct.id
        if not isinstance(acct_id, str) or not acct_id.strip():
            raise VaultUpgradeError(
                "Invalid account identifier encountered during vault upgrade"
            )

        if acct_id in seen:
            raise VaultUpgradeError(
                "Duplicate account identifier encountered during vault upgrade"
            )

        seen.add(acct_id)
        result[acct_id] = acct

    # Verify the ordered list of IDs matches exactly.
    actual_ids = tuple(acct.id for acct in accounts)  # type: ignore[union-attr]
    if actual_ids != expected_ids:
        raise VaultUpgradeError(
            "Account order mismatch during vault upgrade"
        )

    return result


def _build_v2_candidate(
    directory: Path,
    master_password: str,
    accounts: tuple[Account, ...],
) -> Path:
    """Build an isolated version-2 vault candidate from decrypted accounts.

    Validates *accounts* upfront, creates a unique hidden temporary file
    in *directory*, initialises it as a v2 vault with *master_password*,
    and re-encrypts every account into the new vault.

    Input ``Account`` objects are never mutated.

    Args:
        directory: Parent directory for the candidate vault file.
        master_password: Master password for the new v2 vault.
        accounts: Accounts to encrypt into the candidate.

    Returns:
        Path to the completed candidate vault file with mode ``0o600``.

    Raises:
        VaultUpgradeError: If validation, vault setup, or account
            insertion fails.  Error messages do not contain secrets or
            account fields.
    """
    # Validate accounts upfront – reject malformed / duplicate IDs.
    _account_map(tuple(getattr(acct, "id", None) for acct in accounts), accounts)  # type: ignore[arg-type]

    fd: int = -1
    candidate_path: Path | None = None
    manager: VaultManager | None = None

    try:
        # Create unique hidden temporary file in the same filesystem.
        fd, tmp_name = tempfile.mkstemp(
            prefix=".vault-v2-candidate-",
            suffix=".json",
            dir=str(directory),
        )
        candidate_path = Path(tmp_name)
        os.chmod(candidate_path, 0o600)
        os.close(fd)
        fd = -1

        # Initialise empty v2 vault.
        manager = VaultManager(str(candidate_path))
        if not manager.setup_master_password(master_password):
            raise VaultUpgradeError(
                "Failed to initialise vault candidate"
            )

        # Unlock so we can add accounts.
        if not manager.unlock(master_password):
            raise VaultUpgradeError(
                "Failed to unlock vault candidate"
            )

        # Re-encrypt every account into the new vault.
        for account in accounts:
            if not manager.add_account(account):
                raise VaultUpgradeError(
                    "Failed to add account to vault candidate"
                )

        # Success – seal the manager and return the path.
        manager.lock()
        manager.close()
        manager = None

        # Ensure mode is owner-only before returning.
        candidate_path.chmod(0o600)
        return candidate_path

    except VaultUpgradeError:
        # Clean up and re-raise the safe error unchanged.
        if manager is not None:
            with suppress(Exception):
                manager.lock()
            with suppress(Exception):
                manager.close()
        if fd >= 0:
            os.close(fd)
        if candidate_path is not None and candidate_path.exists():
            with suppress(Exception):
                candidate_path.unlink()
        raise

    except Exception:
        # Translate unexpected errors to safe VaultUpgradeError.
        if manager is not None:
            with suppress(Exception):
                manager.lock()
            with suppress(Exception):
                manager.close()
        if fd >= 0:
            os.close(fd)
        if candidate_path is not None and candidate_path.exists():
            with suppress(Exception):
                candidate_path.unlink()
        raise VaultUpgradeError(
            "Failed to build vault candidate"
        ) from None


def _verify_v2_accounts(
    path: Path,
    master_password: str,
    expected_accounts: tuple[Account, ...],
) -> str:
    """Verify a version-2 vault candidate contains the expected accounts.

    Independently reads and parses the vault file, confirms it is a valid
    v2 document, unlocks it, retrieves all accounts, and compares every
    dataclass field against *expected_accounts*.

    Args:
        path: Filesystem path to the v2 vault candidate.
        master_password: Master password to unlock the vault.
        expected_accounts: The accounts expected in the vault, in order.

    Returns:
        SHA-256 hex digest of the verified vault file.

    Raises:
        VaultUpgradeError: If the file is inaccessible, not a regular
            v2 vault, fails to unlock, or account data does not match.
            Error messages do not contain secrets or account fields.
    """
    manager: VaultManager | None = None

    try:
        # --- Preflight: path validation ---
        try:
            st = path.lstat()
        except OSError:
            raise VaultUpgradeError(
                "Vault candidate is unavailable"
            ) from None

        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise VaultUpgradeError(
                "Vault candidate is not a regular file"
            )

        if stat.S_IMODE(st.st_mode) != 0o600:
            raise VaultUpgradeError(
                "Vault candidate permissions are insecure"
            )

        # --- Independent read and parse ---
        try:
            text = path.read_text(encoding="utf-8")
            document: dict[str, object] = json.loads(text)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise VaultUpgradeError(
                "Vault candidate is not valid JSON"
            ) from None

        if not isinstance(document, dict):
            raise VaultUpgradeError(
                "Vault candidate is not a valid JSON object"
            )

        # Must be a recognised v2 document.
        if detect_version(document) != 2:
            raise VaultUpgradeError(
                "Vault candidate format is invalid"
            )
        if not VaultFormat.validate_vault_format(document):
            raise VaultUpgradeError(
                "Vault candidate format is invalid"
            )

        # --- Open and unlock ---
        manager = VaultManager(str(path))
        if not manager.unlock(master_password):
            raise VaultUpgradeError(
                "Vault candidate password is invalid or data is unreadable"
            )

        # --- Validate expected accounts ---
        expected_ids = tuple(acct.id for acct in expected_accounts)  # type: ignore[arg-type]
        expected_map = _account_map(expected_ids, expected_accounts)

        # --- Retrieve vault accounts ---
        vault_accounts = tuple(manager.get_all_accounts())

        # Validate vault accounts via _account_map (checks every entry is
        # Account, IDs are non-empty str, unique, and match expected order).
        vault_map = _account_map(expected_ids, vault_accounts)

        # --- Compare every dataclass field for every account ---
        for acct_id in expected_ids:
            vault_acct = vault_map[acct_id]
            expected_acct = expected_map[acct_id]
            if vault_acct != expected_acct:
                raise VaultUpgradeError(
                    "Vault candidate account data does not match expected"
                )

        # --- Success ---
        manager.lock()
        manager.close()
        manager = None

        return _sha256_file(path)

    except VaultUpgradeError:
        if manager is not None:
            with suppress(Exception):
                manager.lock()
            with suppress(Exception):
                manager.close()
        raise

    except Exception:
        if manager is not None:
            with suppress(Exception):
                manager.lock()
            with suppress(Exception):
                manager.close()
        raise VaultUpgradeError(
            "Vault candidate verification failed"
        ) from None


def _cleanup_candidate(candidate: Path | None) -> None:
    """Best-effort removal of an owned temporary candidate file."""
    if candidate is not None:
        with suppress(Exception):
            if candidate.exists():
                candidate.unlink()


def _restore_v1_backup(backup_path: Path, target_path: Path) -> bool:
    """Restore a version-1 vault from backup atomically.

    Never modifies or deletes *backup_path*.  On success the restored
    *target_path* is owned by the current user with mode ``0o600``.

    Args:
        backup_path: Path to the backup file (never modified/deleted).
        target_path: Path to replace with restored backup.

    Returns:
        ``True`` if the restore succeeded, ``False`` on any failure
        (no exception is raised to the caller).
    """
    fd: int = -1
    temp_path: Path | None = None

    try:
        # Require backup is a regular non-symlink file.
        try:
            st = backup_path.lstat()
        except OSError:
            return False

        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            return False

        # Compute backup hash before any filesystem writes.
        backup_hash = _sha256_file(backup_path)

        # Create a unique hidden temporary file in the target parent.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target_path.name}.v1-rollback-",
            suffix=".tmp",
            dir=str(target_path.parent),
        )
        temp_path = Path(tmp_name)
        os.chmod(temp_path, 0o600)

        # Stream raw backup bytes into the temporary file.
        with os.fdopen(fd, "wb") as f:
            fd = -1  # fd is now owned by the file object
            with backup_path.open("rb") as src:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            f.flush()
            os.fsync(f.fileno())

        # Require temporary file hash matches the backup hash.
        temp_hash = _sha256_file(temp_path)
        if temp_hash != backup_hash:
            return False

        # Atomically replace target with restored content.
        os.replace(temp_path, target_path)
        temp_path = None  # no longer own this path

        # Require restored file hash matches the backup hash.
        if _sha256_file(target_path) != backup_hash:
            return False

        # Require restored file has owner-only mode 0600.
        if stat.S_IMODE(target_path.stat().st_mode) != 0o600:
            return False

        return True

    except Exception:
        return False

    finally:
        # Close fd if still owned by this function.
        if fd >= 0:
            with suppress(Exception):
                os.close(fd)

        # Best-effort unlink of owned temporary file only.
        if temp_path is not None:
            with suppress(Exception):
                if temp_path.exists():
                    temp_path.unlink()


def inspect_vault_version(path: Path) -> int:
    """Read-only probe of vault file format version.

    Returns 1 for v1 ("1.0"), 2 for v2 (integer 2).

    Raises VaultUpgradeError for inaccessible path, non-regular file,
    invalid UTF-8 JSON, non-dict content, unknown version, or format
    validation failure. Side-effect-free: does not modify file bytes,
    mtime, mode, or inode.
    """
    try:
        st = path.lstat()
    except OSError:
        raise VaultUpgradeError("Vault file is inaccessible") from None

    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise VaultUpgradeError("Vault file is not a regular file")

    try:
        text = path.read_text(encoding="utf-8")
        data: dict[str, object] = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VaultUpgradeError("Vault file is not valid UTF-8 JSON") from None

    if not isinstance(data, dict):
        raise VaultUpgradeError("Vault file is not a valid JSON object")

    version = detect_version(data)
    if version == 1:
        if not VaultFormat.validate_vault_format(data):
            raise VaultUpgradeError("Vault file format is invalid")
        return 1
    if version == 2:
        if not VaultFormat.validate_vault_format(data):
            raise VaultUpgradeError("Vault file format is invalid")
        return 2

    raise VaultUpgradeError("Vault file version is unsupported")


def upgrade_vault_v1_to_v2(
    path: Path,
    master_password: str,
) -> VaultUpgradeResult:
    """Upgrade a version-1 vault to version-2 in-place with safety checks.

    Orchestrates existing helpers in a strict sequence with integrity
    verification at every stage.  On failure, secret-safe metadata is
    provided for recovery.

    Args:
        path: Filesystem path to the version-1 vault file.
        master_password: The master password to unlock the vault.

    Returns:
        ``VaultUpgradeResult`` describing the upgrade.

    Raises:
        VaultUpgradeError: If any stage of the upgrade fails.
            Error messages and embedded metadata never contain
            passwords or account field values.
    """
    # ── Step 1: Load, validate, and hash source ──────────────────────
    doc = _load_source_document(path)
    expected_ids = _validate_raw_accounts(doc)
    source_hash = _sha256_file(path)

    # ── State tracking ───────────────────────────────────────────────
    backup_info: _BackupInfo | None = None
    candidate_path: Path | None = None
    source_replaced: bool = False

    try:
        # ── Step 2: Snapshot accounts with integrity re-check ────────
        accounts = _snapshot_v1_accounts(path, master_password, expected_ids)

        if _sha256_file(path) != source_hash:
            raise VaultUpgradeError(
                "Vault source changed after account decryption"
            )

        # ── Step 3: Create secure backup ─────────────────────────────
        backup_info = _create_secure_backup(path)

        if backup_info.sha256 != source_hash:
            raise VaultUpgradeError(
                "Vault backup hash does not match original source hash"
            )

        # ── Step 4: Build and verify v2 candidate ────────────────────
        candidate_path = _build_v2_candidate(
            path.parent, master_password, accounts
        )
        candidate_hash = _verify_v2_accounts(
            candidate_path, master_password, accounts
        )

        # ── Step 5: Pre-replacement source integrity check ───────────
        if _sha256_file(path) != source_hash:
            raise VaultUpgradeError(
                "Vault source changed before replacement"
            )

        # ── Step 6: Atomic replacement ───────────────────────────────
        os.replace(candidate_path, path)
        candidate_path = None  # no longer own the file
        source_replaced = True

        # ── Step 7: Post-replacement verification ────────────────────
        installed_hash = _verify_v2_accounts(
            path, master_password, accounts
        )
        if installed_hash != candidate_hash:
            raise VaultUpgradeError(
                "Vault candidate hash mismatch after replacement"
            )

        # ── Step 8: Backup cleanup ───────────────────────────────────
        try:
            backup_info.path.unlink()
            backup_deleted = True
            retained_path: str | None = None
        except Exception:
            backup_deleted = False
            retained_path = str(backup_info.path)

        return VaultUpgradeResult(
            source_version=1,
            target_version=2,
            accounts_reencrypted=len(accounts),
            source_sha256=source_hash,
            target_sha256=installed_hash,
            backup_deleted=backup_deleted,
            retained_backup_path=retained_path,
        )

    except Exception as exc:
        _cleanup_candidate(candidate_path)

        if isinstance(exc, VaultUpgradeError):
            error_message = str(exc)
        else:
            error_message = "Vault upgrade failed"

        if backup_info is not None:
            if source_replaced:
                # Attempt rollback only after source was replaced.
                # First verify backup integrity, then restore.
                try:
                    if _sha256_file(backup_info.path) != backup_info.sha256:
                        rollback_succeeded = False
                    else:
                        rollback_succeeded = _restore_v1_backup(
                            backup_info.path, path
                        )
                except Exception:
                    rollback_succeeded = False
            else:
                rollback_succeeded = None

            raise VaultUpgradeError(
                error_message,
                rollback_succeeded=rollback_succeeded,
                recovery_backup_path=str(backup_info.path),
                source_sha256=source_hash,
                backup_sha256=backup_info.sha256,
            ) from None
        else:
            raise VaultUpgradeError(
                error_message,
                rollback_succeeded=None,
                source_sha256=source_hash,
            ) from None
