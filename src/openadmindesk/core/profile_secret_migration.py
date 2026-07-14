"""Explicit migration of legacy plaintext profile secrets into the vault."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

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
