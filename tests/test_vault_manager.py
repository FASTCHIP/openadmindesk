"""Tests for vault manager."""

import tempfile
import os
import stat
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.account import Account


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


