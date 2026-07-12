"""Explicit migration of legacy plaintext profile secrets into the vault."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from openadmindesk.core.account import Account
from openadmindesk.core.vault_manager import VaultManager

SECRET_COLUMNS = ("password", "private_key_passphrase", "rdp_gateway_password")


@dataclass(frozen=True)
class ProfileSecretMigrationResult:
    scanned: int = 0
    migrated: int = 0
    cleared_only: int = 0


def migrate_plaintext_profile_secrets(
    db_path: str,
    vault: VaultManager,
    *,
    confirm_cleartext_removal: bool = False,
) -> ProfileSecretMigrationResult:
    """Move legacy profile secrets to vault accounts and clear profile columns.

    This is intentionally explicit and never runs during normal application startup.
    """
    if not confirm_cleartext_removal:
        raise ValueError("explicit cleartext-removal confirmation is required")
    if not vault.is_unlocked():
        raise RuntimeError("vault must be unlocked before migrating profile secrets")

    scanned = migrated = cleared_only = 0
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT name, host, port, username, session_type, credential_id,
                   password, private_key_passphrase, rdp_gateway_password
            FROM profiles
            WHERE password IS NOT NULL
               OR private_key_passphrase IS NOT NULL
               OR rdp_gateway_password IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            scanned += 1
            credential_id = row["credential_id"]
            if row["password"] or row["private_key_passphrase"]:
                account = Account(
                    id=credential_id,
                    name=row["name"],
                    username=row["username"] or "",
                    password=row["password"],
                    private_key_passphrase=row["private_key_passphrase"],
                    host=row["host"] or "",
                    port=row["port"] or 22,
                    service_type=row["session_type"] or "ssh",
                )
                if credential_id:
                    vault.remove_account(credential_id)
                if not vault.add_account(account):
                    raise RuntimeError(f"failed to migrate profile {row['name']!r}")
                credential_id = account.id
                migrated += 1
            elif row["rdp_gateway_password"]:
                cleared_only += 1

            conn.execute(
                """
                UPDATE profiles
                SET credential_id = ?,
                    password = NULL,
                    private_key_passphrase = NULL,
                    rdp_gateway_password = NULL
                WHERE name = ?
                """,
                (credential_id, row["name"]),
            )
        conn.commit()

    return ProfileSecretMigrationResult(
        scanned=scanned,
        migrated=migrated,
        cleared_only=cleared_only,
    )
