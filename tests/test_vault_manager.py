"""Tests for vault manager."""

import asyncio
import tempfile
import os
import stat
import json
import logging
import hashlib
import hmac
import secrets

import pytest

import argon2.low_level
from argon2.low_level import Type as Argon2Type

from openadmindesk.core import vault_manager as vault_manager_module
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.account import Account


# ---- Existing tests (preserved) ----


def test_vault_manager_creation() -> None:
    """Test vault manager creation."""
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        vault_path = tmp.name

    try:
        manager = VaultManager(vault_path)
        assert manager is not None
        assert manager.vault_path == vault_path
    finally:
        # Clean up
        if os.path.exists(vault_path):
            os.unlink(vault_path)


def test_vault_setup_and_unlock() -> None:
    """Test vault setup and unlock."""
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        vault_path = tmp.name

    try:
        manager = VaultManager(vault_path)

        # Setup master password
        success = manager.setup_master_password("testpassword123")
        assert success

        # Unlock with correct password
        unlocked = manager.unlock("testpassword123")
        assert unlocked
        assert manager.is_unlocked()

        # Try to unlock with wrong password
        manager2 = VaultManager(vault_path)
        unlocked2 = manager2.unlock("wrongpassword")
        assert not unlocked2
        assert not manager2.is_unlocked()

        # Lock the vault
        manager.lock()
        assert not manager.is_unlocked()

    finally:
        # Clean up
        if os.path.exists(vault_path):
            os.unlink(vault_path)

def test_vault_save_uses_restrictive_permissions(tmp_path) -> None:
    """Saved vault files should be readable/writable only by the owner."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))

    assert manager.setup_master_password("testpassword123")

    mode = stat.S_IMODE(os.stat(vault_path).st_mode)
    assert mode == 0o600


def test_vault_save_cleans_up_temporary_files(tmp_path) -> None:
    """Atomic vault saves should not leave temp files next to the vault."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))

    assert manager.setup_master_password("testpassword123")

    assert list(tmp_path.glob(".vault-*.tmp")) == []
    assert vault_path.exists()

def test_vault_auto_locks_after_idle_timeout(tmp_path, monkeypatch) -> None:
    """Unlocked vaults should lock themselves after the configured idle timeout."""
    current_time = [1000.0]
    monkeypatch.setattr("openadmindesk.core.vault_manager.time.time", lambda: current_time[0])

    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path), auto_lock_timeout_seconds=10)
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")
    assert manager.is_unlocked()

    current_time[0] += 9
    assert manager.is_unlocked()

    current_time[0] += 1
    assert not manager.is_unlocked()


def test_vault_auto_lock_can_be_disabled(tmp_path, monkeypatch) -> None:
    """A None timeout keeps the vault unlocked until explicit lock()."""
    current_time = [1000.0]
    monkeypatch.setattr("openadmindesk.core.vault_manager.time.time", lambda: current_time[0])

    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path), auto_lock_timeout_seconds=None)
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    current_time[0] += 100000
    assert manager.is_unlocked()


def test_add_account_preserves_original_account(tmp_path) -> None:
    """Test that add_account doesn't mutate the original Account object."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Create an account with sensitive data
    original_account = Account(
        id="test_id",
        name="Test Account",
        username="testuser",
        password="secret_password",
        private_key="private_key_content",
        private_key_passphrase="passphrase",
        host="192.168.1.1",
        port=22
    )

    # Store original plaintext values
    original_password = original_account.password
    original_private_key = original_account.private_key
    original_private_key_passphrase = original_account.private_key_passphrase

    # Add account to vault
    success = manager.add_account(original_account)
    assert success

    # Verify original account is unchanged
    assert original_account.password == original_password
    assert original_account.private_key == original_private_key
    assert original_account.private_key_passphrase == original_private_key_passphrase

    # Verify account can be retrieved with decrypted values
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is not None
    assert retrieved_account.password == "secret_password"
    assert retrieved_account.private_key == "private_key_content"
    assert retrieved_account.private_key_passphrase == "passphrase"


def test_add_account_upsert_by_id(tmp_path) -> None:
    """Test that add_account properly upserts by account ID."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add first account
    account1 = Account(
        id="test_id",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1)
    assert success

    # Verify account was added
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "First Account"

    # Add account with same ID but different values (should upsert)
    account2 = Account(
        id="test_id",
        name="Second Account",
        username="user2",
        password="password2",
        host="192.168.1.2",
        port=23
    )

    success = manager.add_account(account2)
    assert success

    # Verify account was updated (only one account, with new values)
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "Second Account"
    assert accounts[0].username == "user2"
    assert accounts[0].password == "password2"
    assert accounts[0].host == "192.168.1.2"
    assert accounts[0].port == 23

    # Verify get_account returns updated values
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is not None
    assert retrieved_account.name == "Second Account"
    assert retrieved_account.username == "user2"
    assert retrieved_account.password == "password2"
    assert retrieved_account.host == "192.168.1.2"
    assert retrieved_account.port == 23


def test_add_account_failure_reverts_changes(tmp_path, monkeypatch) -> None:
    """Test that add_account reverts changes on save failure."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add initial account
    account1 = Account(
        id="test_id_1",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1)
    assert success

    # Add second account
    account2 = Account(
        id="test_id_2",
        name="Second Account",
        username="user2",
        password="password2",
        host="192.168.1.2",
        port=23
    )

    success = manager.add_account(account2)
    assert success

    # Verify both accounts exist
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    # Mock _save_vault to return False to simulate save failure
    monkeypatch.setattr(manager, '_save_vault', lambda: False)

    # Try to add an account that should fail
    account3 = Account(
        id="test_id_3",
        name="Third Account",
        username="user3",
        password="password3",
        host="192.168.1.3",
        port=24
    )

    success = manager.add_account(account3)
    assert not success  # Should return False due to save failure

    # Verify accounts are unchanged (should still be 2 accounts)
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    # Verify original accounts are still there
    retrieved_account1 = manager.get_account("test_id_1")
    assert retrieved_account1 is not None
    assert retrieved_account1.name == "First Account"

    retrieved_account2 = manager.get_account("test_id_2")
    assert retrieved_account2 is not None
    assert retrieved_account2.name == "Second Account"

    # Verify the new account was not added
    retrieved_account3 = manager.get_account("test_id_3")
    assert retrieved_account3 is None


def test_add_account_failure_reverts_changes_on_update(tmp_path, monkeypatch) -> None:
    """Test that add_account reverts changes on save failure during update."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add initial account
    account1 = Account(
        id="test_id",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1)
    assert success

    # Verify account exists
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "First Account"

    # Mock _save_vault to return False to simulate save failure
    monkeypatch.setattr(manager, '_save_vault', lambda: False)

    # Try to update the existing account (should fail)
    account1_updated = Account(
        id="test_id",
        name="Updated Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1_updated)
    assert not success  # Should return False due to save failure

    # Verify account is unchanged
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "First Account"

    # Verify get_account returns original values
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is not None
    assert retrieved_account.name == "First Account"


def test_remove_account_success(tmp_path) -> None:
    """Test that remove_account works correctly and returns True on success."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add an account
    account = Account(
        id="test_id",
        name="Test Account",
        username="testuser",
        password="password123",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account)
    assert success

    # Verify account was added
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1

    # Remove the account
    success = manager.remove_account("test_id")
    assert success

    # Verify account was removed
    accounts = manager.get_all_accounts()
    assert len(accounts) == 0

    # Verify account is no longer retrievable
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is None


def test_remove_account_nonexistent_id(tmp_path) -> None:
    """Test that remove_account returns False when account ID doesn't exist in populated vault."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add some accounts to create a populated vault
    account1 = Account(
        id="existing_id_1",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )
    account2 = Account(
        id="existing_id_2",
        name="Second Account",
        username="user2",
        password="password2",
        host="192.168.1.2",
        port=23
    )

    assert manager.add_account(account1)
    assert manager.add_account(account2)

    # Verify vault is populated
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    # Try to remove non-existent account
    success = manager.remove_account("nonexistent_id")
    assert not success

    # Verify original accounts are unchanged
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    retrieved_account1 = manager.get_account("existing_id_1")
    assert retrieved_account1 is not None
    assert retrieved_account1.name == "First Account"

    retrieved_account2 = manager.get_account("existing_id_2")
    assert retrieved_account2 is not None
    assert retrieved_account2.name == "Second Account"


def test_remove_account_failure_reverts_changes(tmp_path, monkeypatch) -> None:
    """Test that remove_account reverts changes on save failure."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add initial account
    account1 = Account(
        id="test_id_1",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1)
    assert success

    # Add second account
    account2 = Account(
        id="test_id_2",
        name="Second Account",
        username="user2",
        password="password2",
        host="192.168.1.2",
        port=23
    )

    success = manager.add_account(account2)
    assert success

    # Verify both accounts exist
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    # Mock _save_vault to return False to simulate save failure
    monkeypatch.setattr(manager, '_save_vault', lambda: False)

    # Try to remove an account that should fail
    success = manager.remove_account("test_id_1")
    assert not success  # Should return False due to save failure

    # Verify accounts are unchanged (should still be 2 accounts)
    accounts = manager.get_all_accounts()
    assert len(accounts) == 2

    # Verify original accounts are still there
    retrieved_account1 = manager.get_account("test_id_1")
    assert retrieved_account1 is not None
    assert retrieved_account1.name == "First Account"

    retrieved_account2 = manager.get_account("test_id_2")
    assert retrieved_account2 is not None
    assert retrieved_account2.name == "Second Account"

    # Verify the account was not actually removed
    retrieved_account3 = manager.get_account("test_id_3")
    assert retrieved_account3 is None


def test_remove_account_runtime_error_reverts_changes(tmp_path, monkeypatch) -> None:
    """Test that remove_account handles RuntimeError during save and reverts changes."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add initial account
    account1 = Account(
        id="test_id",
        name="First Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(account1)
    assert success

    # Verify account exists
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "First Account"

    # Mock _save_vault to raise RuntimeError to simulate save failure
    def raise_runtime_error():
        raise RuntimeError("Simulated save error")

    monkeypatch.setattr(manager, '_save_vault', raise_runtime_error)

    # Try to remove the account (should fail with RuntimeError)
    success = manager.remove_account("test_id")
    assert not success  # Should return False due to RuntimeError

    # Verify account is unchanged
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "First Account"

    # Verify get_account returns original values
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is not None
    assert retrieved_account.name == "First Account"


def test_add_account_runtime_error_during_update(tmp_path, monkeypatch) -> None:
    """Test that add_account handles RuntimeError during UPDATE and reverts changes."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")
    assert manager.unlock("testpassword123")

    # Add initial account
    original_account = Account(
        id="test_id",
        name="Original Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(original_account)
    assert success

    # Verify account exists
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "Original Account"

    # Mock _save_vault to raise RuntimeError to simulate save failure
    def raise_runtime_error():
        raise RuntimeError("Simulated save error")

    monkeypatch.setattr(manager, '_save_vault', raise_runtime_error)

    # Try to update the existing account (should fail with RuntimeError)
    updated_account = Account(
        id="test_id",
        name="Updated Account",
        username="user1",
        password="password1",
        host="192.168.1.1",
        port=22
    )

    success = manager.add_account(updated_account)
    assert not success  # Should return False due to RuntimeError

    # Verify account is unchanged
    accounts = manager.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "Original Account"

    # Verify get_account returns original values
    retrieved_account = manager.get_account("test_id")
    assert retrieved_account is not None
    assert retrieved_account.name == "Original Account"


# ---- New Phase 9.9a tests ----


def _create_vault_file(path, data):
    """Helper to write vault JSON data to a file."""
    with open(path, "w") as f:
        json.dump(data, f)


def _derive_key_for_test(password, salt_hex, iterations=100000, length=32):
    """Helper to derive a key for test vault creation."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    salt = bytes.fromhex(salt_hex)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return kdf.derive(password.encode())


def _make_v1_data(salt_hex, key_hash, password, kdf_params=None, iterations=100000, length=32):
    """Helper to create v1 vault data dict.

    Builds the key_hash from password+salt+iterations when key_hash is empty.
    """
    import hashlib as hl
    if not key_hash:
        key = _derive_key_for_test(password, salt_hex, iterations=iterations, length=length)
        key_hash = hl.sha256(key).hexdigest()[:16]

    data = {
        "version": "1.0",
        "salt": salt_hex,
        "key_hash": key_hash,
        "accounts": []
    }
    if kdf_params is not None:
        data["kdf_params"] = kdf_params
    return data


def test_legacy_v1_without_metadata_unlocks(tmp_path) -> None:
    """Legacy v1 vault without metadata/kdf_params still unlocks."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    # Create old-style vault data (no metadata, no iv/ciphertext)
    data = _make_v1_data(salt_hex, "", password="testpassword", iterations=100000)
    # Deliberately remove iv/ciphertext to simulate old-style vault
    data.pop("iv", None)
    data.pop("ciphertext", None)
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert manager.unlock("testpassword")
    assert manager.is_unlocked()


def test_v2_has_kdf_params_and_timestamps(tmp_path) -> None:
    """New v2 vault setup writes argon2id kdf params and timestamps."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")

    with open(vault_path) as f:
        data = json.load(f)

    assert data["kdf"] == "argon2id"
    assert data["kdf_params"]["time_cost"] == 2
    assert data["kdf_params"]["memory_cost"] == 19456
    assert data["kdf_params"]["parallelism"] == 1
    assert data["kdf_params"]["hash_len"] == 32
    assert data["kdf_params"]["version"] == 19
    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] == data["updated_at"]
    assert "key_hash" not in data
    assert "iv" not in data
    assert "ciphertext" not in data
    assert len(data["salt"]) == 32
    assert len(data["password_hash"]) == 64


def test_v2_unlocks_with_correct_password(tmp_path) -> None:
    """New v2 vault with argon2id unlocks with correct password."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")

    # Fresh manager unlocks with correct password
    manager2 = VaultManager(str(vault_path))
    assert manager2.unlock("testpassword123")
    assert manager2.is_unlocked()


def test_vault_missing_key_hash_rejected(tmp_path) -> None:
    """Vault without key_hash field is rejected."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "accounts": []
    }
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_malformed_v2_rejected(tmp_path) -> None:
    """Malformed v2 vault data is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": 2,
        "salt": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "kdf": "argon2id",
        "kdf_params": {},
        "password_hash": "abc123",
        "accounts": [],
        "created_at": "t",
        "updated_at": "t"
    }
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unknown_version_rejected(tmp_path) -> None:
    """Unknown vault version is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": 99,
        "salt": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "accounts": []
    }
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_stored_iterations_used(tmp_path) -> None:
    """Vault with valid custom iterations uses those iterations for key derivation."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "b1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    custom_iterations = 200000
    data = _make_v1_data(salt_hex, "", password="mypassword", iterations=custom_iterations)
    data["kdf_params"] = {"iterations": custom_iterations, "length": 32}
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert manager.unlock("mypassword")
    assert manager.is_unlocked()


def test_unsafe_iterations_bounded_and_fails(tmp_path) -> None:
    """Unsafe iterations (< 100000) are bounded to default, causing unlock failure."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "c1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    low_iterations = 50000
    data = _make_v1_data(salt_hex, "", password="mypassword", iterations=low_iterations)
    data["kdf_params"] = {"iterations": low_iterations, "length": 32}
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    # Key derived with 50000 won't match after safe bounds enforcement uses 100000
    assert not manager.unlock("mypassword")


def test_unsafe_length_bounded_and_fails(tmp_path) -> None:
    """Non-32 length is bounded to 32, causing unlock failure."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "d1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    # Derive key_hash with length=64, then store params claiming length=64
    data = _make_v1_data(salt_hex, "", password="mypassword", iterations=100000, length=64)
    data["kdf_params"] = {"iterations": 100000, "length": 64}
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    # Safe bounds reset length to 32, so key derivation uses different params
    assert not manager.unlock("mypassword")


def test_wrong_password_rejected_with_compare_digest(tmp_path) -> None:
    """Wrong password is rejected regardless of key_hash comparison method."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("correctpassword")

    manager2 = VaultManager(str(vault_path))
    assert not manager2.unlock("wrongpassword")
    assert not manager2.is_unlocked()


def test_updated_at_changes_on_save(tmp_path) -> None:
    """_save_vault updates updated_at when metadata is present."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")

    # Read initial updated_at
    with open(vault_path) as f:
        data = json.load(f)
    initial_updated = data["updated_at"]

    # Call _save_vault again (e.g., after unlocking)
    assert manager.unlock("testpassword")
    # Add an account to trigger save
    account = Account(
        id="save_test",
        name="Save Test",
        username="user",
        password="pass",
        host="localhost",
        port=22
    )
    assert manager.add_account(account)

    # Read updated updated_at
    with open(vault_path) as f:
        data = json.load(f)
    new_updated = data["updated_at"]

    # updated_at should have been updated
    assert new_updated >= initial_updated


def test_legacy_v1_without_iv_cipher_is_still_writable(tmp_path) -> None:
    """Legacy v1 vault without iv/ciphertext can be unlocked and modified."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "e1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    data = _make_v1_data(salt_hex, "", password="testpassword", iterations=100000)
    # Remove optional fields to simulate old vault
    data.pop("iv", None)
    data.pop("ciphertext", None)
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert manager.unlock("testpassword")

    # Add an account
    account = Account(
        id="write_test",
        name="Write Test",
        username="user",
        password="pass",
        host="localhost",
        port=22
    )
    assert manager.add_account(account)
    assert manager.get_account("write_test") is not None


def test_serialization_roundtrip_v2_with_metadata(tmp_path) -> None:
    """Serialize and deserialize roundtrip preserves v2 argon2id metadata."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")
    assert manager.unlock("testpassword")

    # Lock and re-load
    manager.lock()

    manager2 = VaultManager(str(vault_path))
    assert manager2.unlock("testpassword")
    assert manager2._vault_data is not None
    assert manager2._vault_data.get("kdf") == "argon2id"
    assert manager2._vault_data.get("kdf_params")["time_cost"] == 2
    assert manager2._vault_data.get("kdf_params")["hash_len"] == 32


def test_create_empty_v1_explicitly() -> None:
    """create_empty_vault can explicitly create v1 vault."""
    from openadmindesk.core.vault_format import VaultFormat, LEGACY_VERSION
    vault = VaultFormat.create_empty_vault(version=LEGACY_VERSION)
    assert vault["version"] == "1.0"


def test_detect_version_from_manager_vault(tmp_path) -> None:
    """VaultManager setup creates vault detectable as v2."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")

    with open(vault_path) as f:
        data = json.load(f)

    from openadmindesk.core.vault_format import detect_version
    assert detect_version(data) == 2


def test_kdf_params_absent_uses_defaults(tmp_path) -> None:
    """Vault without kdf_params still unlocks using default iterations/length."""
    vault_path = tmp_path / "vault.json"
    salt_hex = "f1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    data = _make_v1_data(salt_hex, "", password="testpass", iterations=100000)
    # Ensure no kdf_params
    data.pop("kdf_params", None)
    _create_vault_file(vault_path, data)

    manager = VaultManager(str(vault_path))
    assert manager.unlock("testpass")
    assert manager.is_unlocked()


def test_empty_vault_file_returns_false(tmp_path) -> None:
    """Non-existent or empty vault file returns False from unlock."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_corrupt_vault_file_returns_false(tmp_path) -> None:
    """Corrupt vault JSON returns False from unlock."""
    vault_path = tmp_path / "vault.json"
    with open(vault_path, "w") as f:
        f.write("this is not json")

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unlock_rejects_empty_salt(tmp_path) -> None:
    """Vault with empty salt string is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "",
        "key_hash": "deadbeef12345678",
        "accounts": []
    }
    _create_vault_file(vault_path, data)
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unlock_rejects_empty_key_hash(tmp_path) -> None:
    """Vault with empty key_hash string is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "abcdef0123456789abcdef0123456789",
        "key_hash": "",
        "accounts": []
    }
    _create_vault_file(vault_path, data)
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unlock_rejects_bad_hex_salt(tmp_path) -> None:
    """Vault with non-hex salt characters is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        "key_hash": "deadbeef12345678",
        "accounts": []
    }
    _create_vault_file(vault_path, data)
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unlock_rejects_bad_hex_key_hash(tmp_path) -> None:
    """Vault with non-hex key_hash characters is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "abcdef0123456789abcdef0123456789",
        "key_hash": "zzzzzzzzzzzzzzzz",
        "accounts": []
    }
    _create_vault_file(vault_path, data)
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_unlock_rejects_short_salt(tmp_path) -> None:
    """Vault with too-short salt (non-empty, wrong hex length) is rejected."""
    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": "abcdef01",
        "key_hash": "deadbeef12345678",
        "accounts": []
    }
    _create_vault_file(vault_path, data)
    manager = VaultManager(str(vault_path))
    assert not manager.unlock("anypassword")


def test_save_vault_failure_restores_updated_at(tmp_path, monkeypatch) -> None:
    """_save_vault failure restores prior updated_at in-memory."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")
    assert manager.unlock("testpassword")

    # Record the current updated_at value
    prior_updated = manager._vault_data["updated_at"]

    # Monkeypatch os.replace to fail on the next _save_vault call
    original_replace = os.replace
    call_count = [0]

    def failing_replace(src, dst):
        call_count[0] += 1
        raise OSError("Simulated replace failure")

    monkeypatch.setattr(os, "replace", failing_replace)

    # Add an account, which calls _save_vault and should fail
    account = Account(
        id="fail_test", name="Fail Test", username="u",
        password="p", host="localhost", port=22
    )
    success = manager.add_account(account)
    assert not success

    # Restore os.replace so further operations work
    monkeypatch.setattr(os, "replace", original_replace)

    # Verify updated_at was restored to prior value
    assert manager._vault_data["updated_at"] == prior_updated

    # Verify the vault file on disk was not changed
    manager2 = VaultManager(str(vault_path))
    assert manager2.unlock("testpassword")
    # Confirm account was NOT added
    assert manager2.get_account("fail_test") is None

    # Verify mode is still 0600 on a subsequent successful save
    another = Account(
        id="ok_after_fail", name="OK", username="u",
        password="p", host="localhost", port=22
    )
    assert manager.add_account(another)
    mode = stat.S_IMODE(os.stat(vault_path).st_mode)
    assert mode == 0o600

# ---- Phase 9.9b v2-specific tests ----

def _make_v2_vault_file(path, password, salt_hex=None, kdf_params_override=None,
                        password_hash_override=None):
    """Write a valid v2 vault file for a given password.

    Returns (salt_hex, kdf_params, password_hash) used.
    """
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    salt = bytes.fromhex(salt_hex)

    kdf_params = {
        "time_cost": 2,
        "memory_cost": 19456,
        "parallelism": 1,
        "hash_len": 32,
        "version": argon2.low_level.ARGON2_VERSION,
    }
    if kdf_params_override is not None:
        kdf_params.update(kdf_params_override)

    if password_hash_override is not None:
        password_hash = password_hash_override
    else:
        key = argon2.low_level.hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=kdf_params["time_cost"],
            memory_cost=kdf_params["memory_cost"],
            parallelism=kdf_params["parallelism"],
            hash_len=kdf_params["hash_len"],
            type=Argon2Type.ID,
            version=kdf_params["version"],
        )
        context = b"openadmindesk-vault-v2-verifier"
        password_hash = hmac.new(key, context, hashlib.sha256).hexdigest()

    data = {
        "version": 2,
        "salt": salt_hex,
        "kdf": "argon2id",
        "kdf_params": kdf_params,
        "password_hash": password_hash,
        "accounts": [],
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z",
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return salt_hex, kdf_params, password_hash

def test_v2_password_hash_tamper_rejected(tmp_path) -> None:
    """V2 vault with tampered password_hash is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="correctpassword")

    manager = VaultManager(str(vault_path))
    assert manager.unlock("correctpassword")

    # Tamper with password_hash
    with open(vault_path) as f:
        data = json.load(f)
    data["password_hash"] = "0" * 64
    with open(vault_path, "w") as f:
        json.dump(data, f)

    # Fresh manager should fail to unlock
    manager2 = VaultManager(str(vault_path))
    assert not manager2.unlock("correctpassword")
    assert not manager2.is_unlocked()


def test_v2_salt_tamper_rejected(tmp_path) -> None:
    """V2 vault with tampered salt is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="correctpassword")

    manager = VaultManager(str(vault_path))
    assert manager.unlock("correctpassword")

    # Tamper with salt
    with open(vault_path) as f:
        data = json.load(f)
    data["salt"] = "f" * 32
    with open(vault_path, "w") as f:
        json.dump(data, f)

    # Fresh manager should fail to unlock
    manager2 = VaultManager(str(vault_path))
    assert not manager2.unlock("correctpassword")

def test_v2_empty_salt_rejected(tmp_path) -> None:
    """V2 vault with empty salt string is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="testpassword", salt_hex="f" * 32)

    # Mutate salt to empty string
    with open(vault_path) as f:
        data = json.load(f)
    data["salt"] = ""
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("testpassword")


def test_v2_empty_password_hash_rejected(tmp_path) -> None:
    """V2 vault with empty password_hash string is rejected by unlock."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(str(vault_path), "pwd", salt_hex="e" * 32)

    # Mutate password_hash to empty string
    with open(vault_path) as f:
        data = json.load(f)
    data["password_hash"] = ""
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("pwd")


def test_v2_params_missing_key_rejected_before_derive(tmp_path, monkeypatch) -> None:
    """V2 vault with missing kdf_params key is rejected before key derivation."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="testpassword")

    # Remove a required kdf_params key
    with open(vault_path) as f:
        data = json.load(f)
    data["kdf_params"].pop("time_cost")
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    called = [False]
    original = manager._derive_key_v2

    def spy_derive(*args, **kwargs):
        called[0] = True
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "_derive_key_v2", spy_derive)

    assert not manager.unlock("testpassword")
    assert not called[0]


def test_v2_params_bool_rejected_before_derive(tmp_path, monkeypatch) -> None:
    """V2 vault with boolean kdf_params value is rejected before key derivation."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="testpassword")

    # Mutate a kdf_params value to boolean
    with open(vault_path) as f:
        data = json.load(f)
    data["kdf_params"]["time_cost"] = True
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    called = [False]
    original = manager._derive_key_v2

    def spy_derive(*args, **kwargs):
        called[0] = True
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "_derive_key_v2", spy_derive)

    assert not manager.unlock("testpassword")
    assert not called[0]


def test_v2_params_out_of_range_rejected_before_derive(tmp_path, monkeypatch) -> None:
    """V2 vault with out-of-range kdf_params value is rejected before key derivation."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="testpassword")

    # Mutate memory_cost to out-of-range value
    with open(vault_path) as f:
        data = json.load(f)
    data["kdf_params"]["memory_cost"] = 1
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    called = [False]
    original = manager._derive_key_v2

    def spy_derive(*args, **kwargs):
        called[0] = True
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "_derive_key_v2", spy_derive)

    assert not manager.unlock("testpassword")
    assert not called[0]


def test_v2_params_wrong_version_rejected_before_derive(tmp_path, monkeypatch) -> None:
    """V2 vault with wrong kdf_params version is rejected before key derivation."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(vault_path, password="testpassword")

    # Mutate version to invalid value
    with open(vault_path) as f:
        data = json.load(f)
    data["kdf_params"]["version"] = 99
    with open(vault_path, "w") as f:
        json.dump(data, f)

    manager = VaultManager(str(vault_path))
    called = [False]
    original = manager._derive_key_v2

    def spy_derive(*args, **kwargs):
        called[0] = True
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "_derive_key_v2", spy_derive)

    assert not manager.unlock("testpassword")
    assert not called[0]


def test_v2_argon2_error_returns_false(tmp_path, monkeypatch) -> None:
    """Argon2 exception during unlock returns False (fail closed)."""
    vault_path = tmp_path / "vault.json"
    _make_v2_vault_file(str(vault_path), "testpassword")

    original_hash = argon2.low_level.hash_secret_raw

    def failing_hash(*a, **kw):
        raise argon2.exceptions.Argon2Error("simulated failure")

    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", failing_hash)

    manager = VaultManager(str(vault_path))
    assert not manager.unlock("testpassword")
    assert not manager.is_unlocked()

    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", original_hash)


def test_v2_setup_save_failure_restores_state(tmp_path, monkeypatch):
    """V2 setup with _save_vault failure restores prior _master_key/_vault_data."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))

    # First setup succeeds
    assert manager.setup_master_password("firstpw")

    # Patch _save_vault to fail
    monkeypatch.setattr(manager, "_save_vault", lambda: False)

    # Second setup should fail and restore state
    assert not manager.setup_master_password("secondpw")

    # State should be restored to prior values
    assert manager._master_key is not None
    assert manager._vault_data is not None
    assert manager._vault_data.get("kdf") == "argon2id"

    # Fresh manager should still accept firstpw
    manager2 = VaultManager(str(vault_path))
    assert not manager2.unlock("secondpw")
    assert manager2.unlock("firstpw")


def test_v2_setup_argon2_error_restores_state(tmp_path, monkeypatch):
    """V2 setup with Argon2Error during hash restores prior _master_key/_vault_data."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))

    # First setup succeeds
    assert manager.setup_master_password("firstpw")

    # Capture original hash function
    original_hash = argon2.low_level.hash_secret_raw

    # Make hash_secret_raw raise Argon2Error
    def failing_hash(*args, **kwargs):
        raise argon2.exceptions.Argon2Error("simulated failure")

    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", failing_hash)

    # Second setup should fail and restore state
    assert not manager.setup_master_password("secondpw")

    # State should be restored to prior values
    assert manager._master_key is not None
    assert manager._vault_data is not None

    # Restore original function
    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", original_hash)

    # Fresh manager should still accept firstpw
    manager2 = VaultManager(str(vault_path))
    assert manager2.unlock("firstpw")


def test_v2_setup_never_leaves_stale_state(tmp_path):
    """V2 setup with corrupt vault file leaves _master_key/_vault_data as None."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))

    # Setup succeeds
    assert manager.setup_master_password("goodpw")

    # Corrupt the vault file
    with open(vault_path, "w") as f:
        f.write("corrupt")

    # Fresh manager should fail to unlock and leave state clean
    manager2 = VaultManager(str(vault_path))
    assert not manager2.unlock("goodpw")
    assert not manager2.is_unlocked()
    assert manager2._master_key is None
    assert manager2._vault_data is None


def test_hmac_verifier_deterministic():
    """HMAC verifier produces deterministic output for same key."""
    key1 = b"\x00" * 32
    key2 = b"\x01" * 32

    # Create verifiers
    v1a = VaultManager._compute_v2_verifier(key1)
    v1b = VaultManager._compute_v2_verifier(key1)
    v2 = VaultManager._compute_v2_verifier(key2)

    # All verifiers should be 64-character hex strings
    assert len(v1a) == 64
    assert len(v1b) == 64
    assert len(v2) == 64

    # Same key produces same verifier
    assert v1a == v1b

    # Different keys produce different verifiers
    assert v1a != v2

    # Verify they are valid hex strings
    assert int(v1a, 16)
    assert int(v2, 16)


def test_v1_old_vault_still_unlocks_and_writable(tmp_path):
    """Legacy v1 vault still unlocks and allows account writes."""
    salt_hex = "f1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"

    # Create v1 vault data
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend

    salt = bytes.fromhex(salt_hex)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(b"v1password")
    key_hash = hashlib.sha256(key).hexdigest()[:16]

    vault_path = tmp_path / "vault.json"
    data = {
        "version": "1.0",
        "salt": salt_hex,
        "key_hash": key_hash,
        "accounts": []
    }
    with open(vault_path, "w") as f:
        json.dump(data, f)

    # Unlock v1 vault
    manager = VaultManager(str(vault_path))
    assert manager.unlock("v1password")

    # Add account
    account = Account(
        id="v1_write",
        name="V1 Write",
        username="u",
        password="secret",
        host="localhost",
        port=22
    )
    assert manager.add_account(account)

    # Retrieve account
    retrieved = manager.get_account("v1_write")
    assert retrieved is not None
    assert retrieved.password == "secret"

    manager.lock()
    reloaded = VaultManager(str(vault_path))
    assert reloaded.unlock("v1password")
    reloaded_account = reloaded.get_account("v1_write")
    assert reloaded_account is not None
    assert reloaded_account.password == "secret"


def test_v2_account_round_trip_survives_fresh_manager(tmp_path) -> None:
    vault_path = tmp_path / "vault.json"
    master_password = "master123"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password(master_password)
    assert manager.unlock(master_password)

    account = Account(
        id="test-acc",
        name="Test Account",
        username="user",
        password="secret123",
        private_key="-----BEGIN TEST PRIVATE KEY-----\nkey-data",
        private_key_passphrase="keyphrase123",
        host="example.com",
        port=22,
        service_type="ssh",
    )
    assert manager.add_account(account)

    vault_text = vault_path.read_text(encoding="utf-8")
    assert "secret123" not in vault_text
    assert "keyphrase123" not in vault_text
    assert "-----BEGIN TEST PRIVATE KEY-----" not in vault_text

    manager.lock()
    reloaded = VaultManager(str(vault_path))
    assert reloaded.unlock(master_password)
    reloaded_account = reloaded.get_account("test-acc")
    assert reloaded_account is not None
    assert reloaded_account.password == "secret123"
    assert reloaded_account.private_key == "-----BEGIN TEST PRIVATE KEY-----\nkey-data"
    assert reloaded_account.private_key_passphrase == "keyphrase123"


def test_v2_argon2_failure_does_not_log_master_password(
    tmp_path, caplog, monkeypatch
) -> None:
    vault_path = tmp_path / "vault.json"
    setup_manager = VaultManager(str(vault_path))
    assert setup_manager.setup_master_password("setup-password")
    attempted_password = "testpassword123"

    def failing_hash(*args, **kwargs):
        raise argon2.exceptions.Argon2Error(
            f"simulated failure for {attempted_password}"
        )

    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", failing_hash)
    manager = VaultManager(str(vault_path))
    with caplog.at_level(
        logging.ERROR, logger="openadmindesk.core.vault_manager"
    ):
        result = manager.unlock(attempted_password)

    assert result is False
    assert attempted_password not in caplog.text


def test_vault_manager_executor_shutdown_calls_once(tmp_path, monkeypatch) -> None:
    class FakeExecutor:
        def __init__(self) -> None:
            self.shutdown_calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            self.shutdown_calls.append((wait, cancel_futures))

    fake_executor = FakeExecutor()
    monkeypatch.setattr(
        vault_manager_module,
        "ThreadPoolExecutor",
        lambda *args, **kwargs: fake_executor,
    )
    manager = VaultManager(str(tmp_path / "vault.json"))
    manager.close()
    manager.close()
    assert fake_executor.shutdown_calls == [(False, True)]


def test_vault_manager_raises_error_after_close(tmp_path) -> None:
    manager = VaultManager(str(tmp_path / "vault.json"))
    manager.close()
    with pytest.raises(
        RuntimeError,
        match="^VaultManager executor already closed$",
    ):
        asyncio.run(manager.get_all_accounts_async())


def test_vault_manager_run_blocking_args_forwarding(tmp_path) -> None:
    def combine(prefix: str, *, suffix: str) -> str:
        return f"{prefix}:{suffix}"

    manager = VaultManager(str(tmp_path / "vault.json"))
    try:
        result = asyncio.run(
            manager._run_blocking(combine, "left", suffix="right")
        )
    finally:
        manager.close()
    assert result == "left:right"
