"""Tests for explicit legacy profile secret migration."""

from __future__ import annotations

import sqlite3

import pytest

from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_secret_migration import migrate_plaintext_profile_secrets
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.vault_manager import VaultManager


def _vault(tmp_path) -> VaultManager:
    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    return vault


def test_profile_secret_migration_requires_confirmation(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    vault = _vault(tmp_path)

    with pytest.raises(ValueError):
        migrate_plaintext_profile_secrets(store.db_path, vault)


def test_profile_secret_migration_moves_password_to_vault_and_clears_db(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    assert store.save_profile(Profile(name="Legacy", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("legacy-pass", "key-pass", "Legacy"),
        )
        conn.commit()
    vault = _vault(tmp_path)

    result = migrate_plaintext_profile_secrets(
        store.db_path,
        vault,
        confirm_cleartext_removal=True,
    )

    assert result.scanned == 1
    assert result.migrated == 1
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT credential_id, password, private_key_passphrase FROM profiles WHERE name = ?",
            ("Legacy",),
        ).fetchone()
    assert row[0]
    assert row[1] is None
    assert row[2] is None
    account = vault.get_account(row[0])
    assert account is not None
    assert account.password == "legacy-pass"
    assert account.private_key_passphrase == "key-pass"
