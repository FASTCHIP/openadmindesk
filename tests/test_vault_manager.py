"""Tests for vault manager."""

import tempfile
import os
import stat
from openadmindesk.core.vault_manager import VaultManager


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
