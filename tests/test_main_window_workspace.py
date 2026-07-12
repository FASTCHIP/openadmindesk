"""Tests for main window with workspace container."""

from unittest.mock import patch
from openadmindesk.ui.main_window import MainWindow


class FakeProfileStore:
    def load_all_profiles(self):
        return []

    def load_all_folders(self):
        return []

    def save_profile(self, profile):
        return True


class FakeVaultManager:
    config = None

    def is_unlocked(self) -> bool:
        return False


class FakeSyncConfig:
    enabled = False


class FakeSyncManager:
    def __init__(self, profile_store, vault_manager) -> None:
        self.profile_store = profile_store
        self.vault_manager = vault_manager
        self.config = FakeSyncConfig()


def _window() -> MainWindow:
    with patch('openadmindesk.ui.main_window.ProfileStore', return_value=FakeProfileStore()):
        with patch('openadmindesk.ui.main_window.VaultManager', return_value=FakeVaultManager()):
            with patch('openadmindesk.ui.main_window.SyncManager', FakeSyncManager):
                return MainWindow()


def test_main_window_has_workspace_container() -> None:
    """Main window has workspace container."""
    window = _window()
    
    assert window.workspace_container is not None
    assert window.workspace_layout == "single"


def test_main_window_workspace_layout_switching() -> None:
    """Main window can switch workspace layouts."""
    window = _window()
    
    # Test initial layout
    assert window.workspace_layout == "single"
    assert window.workspace_container.get_current_layout_mode() == "single"
    
    # Test switching to horizontal
    window._set_workspace_layout("horizontal")
    assert window.workspace_layout == "horizontal"
    assert window.workspace_container.get_current_layout_mode() == "horizontal"
    
    # Test switching to vertical
    window._set_workspace_layout("vertical")
    assert window.workspace_layout == "vertical"
    assert window.workspace_container.get_current_layout_mode() == "vertical"
    
    # Test switching to grid
    window._set_workspace_layout("grid")
    assert window.workspace_layout == "grid"
    assert window.workspace_container.get_current_layout_mode() == "grid"
    
    # Test switching back to single
    window._set_workspace_layout("single")
    assert window.workspace_layout == "single"
    assert window.workspace_container.get_current_layout_mode() == "single"


def test_main_window_broadcast_with_multiple_workspaces() -> None:
    """Broadcast methods work with multiple workspace layouts."""
    window = _window()
    
    # Test broadcast connection/disconnection in single layout
    window._set_workspace_layout("single")
    window._connect_broadcast()
    window._disconnect_broadcast()
    
    # Test broadcast connection/disconnection in horizontal layout
    window._set_workspace_layout("horizontal")
    window._connect_broadcast()
    window._disconnect_broadcast()
    
    # Test broadcast connection/disconnection in vertical layout
    window._set_workspace_layout("vertical")
    window._connect_broadcast()
    window._disconnect_broadcast()
    
    # Test broadcast connection/disconnection in grid layout
    window._set_workspace_layout("grid")
    window._connect_broadcast()
    window._disconnect_broadcast()
