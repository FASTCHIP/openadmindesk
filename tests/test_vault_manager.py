"""Tests for vault manager."""

import tempfile
import os
import stat
import json

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


def test_new_v1_has_kdf_params_and_timestamps(tmp_path) -> None:
    """New vault setup writes kdf params and created_at/updated_at."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword123")

    with open(vault_path) as f:
        data = json.load(f)

    assert data["kdf"] == "pbkdf2-sha256"
    assert data["kdf_params"] == {"iterations": 100000, "length": 32}
    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] == data["updated_at"]


def test_new_v1_unlocks_with_correct_password(tmp_path) -> None:
    """New v1 vault with metadata unlocks with correct password."""
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


def test_vault_unknown_version_rejected(tmp_path) -> None:
    """Unknown vault version is rejected by unlock."""
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


def test_serialization_roundtrip_v1_with_metadata(tmp_path) -> None:
    """Serialize and deserialize roundtrip preserves v1 metadata."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")
    assert manager.unlock("testpassword")

    # Lock and re-load
    manager.lock()

    manager2 = VaultManager(str(vault_path))
    assert manager2.unlock("testpassword")
    assert manager2._vault_data is not None
    assert manager2._vault_data.get("kdf") == "pbkdf2-sha256"
    assert manager2._vault_data.get("kdf_params") == {"iterations": 100000, "length": 32}


def test_setup_defaults_to_legacy_version(tmp_path) -> None:
    """create_empty_vault uses LEGACY_VERSION '1.0' for now."""
    from openadmindesk.core.vault_format import VaultFormat
    vault = VaultFormat.create_empty_vault()
    assert vault["version"] == "1.0"


def test_detect_version_from_manager_vault(tmp_path) -> None:
    """VaultManager setup creates vault detectable as v1."""
    vault_path = tmp_path / "vault.json"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password("testpassword")

    with open(vault_path) as f:
        data = json.load(f)

    from openadmindesk.core.vault_format import detect_version
    assert detect_version(data) == 1


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
