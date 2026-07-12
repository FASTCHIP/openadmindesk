"""Additional integration test for active workspace routing."""

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


def test_active_workspace_routing() -> None:
    """Test that new sessions are opened in the active workspace."""
    with patch('openadmindesk.ui.main_window.ProfileStore', return_value=FakeProfileStore()):
        with patch('openadmindesk.ui.main_window.VaultManager', return_value=FakeVaultManager()):
            with patch('openadmindesk.ui.main_window.SyncManager', FakeSyncManager):
                window = MainWindow()

                # Test single layout - should use single workspace
                window._set_workspace_layout("single")
                active_ws = window.workspace_container.get_active_workspace()
                initial_count = active_ws.count()

                # Create a simple profile and open it
                from openadmindesk.core.profile import Profile, SessionType
                profile = Profile(name="TestSession", host="test.com", port=22, session_type=SessionType.SSH)
                window._open_ssh_tab(profile)

                # Verify it was opened in the active workspace
                assert active_ws.count() == initial_count + 1
                assert "TestSession" in active_ws.tabText(active_ws.currentIndex())

                # Test horizontal layout - should use one of the two workspaces
                window._set_workspace_layout("horizontal")
                workspaces = window.workspace_container.get_all_workspaces()
                assert len(workspaces) == 2

                # Create another session
                profile2 = Profile(name="TestSession2", host="test2.com", port=22, session_type=SessionType.SSH)
                window._open_ssh_tab(profile2)

                # Verify it was opened in one of the workspaces
                workspaces = window.workspace_container.get_all_workspaces()

                # Behavior-based checks:
                # 1. Both sessions should be present in the workspaces with exact names
                tab_texts = []
                for ws in workspaces:
                    for i in range(ws.count()):
                        tab_text = ws.tabText(i)
                        tab_texts.append(tab_text)

                assert "TestSession" in tab_texts, f"TestSession not found in tabs: {tab_texts}"
                assert "TestSession2" in tab_texts, f"TestSession2 not found in tabs: {tab_texts}"

                # 2. The second session should be the current tab in the active workspace
                active_ws = window.workspace_container.get_active_workspace()
                active_tab_text = active_ws.tabText(active_ws.currentIndex())
                assert active_tab_text == "TestSession2", f"Second session should be current tab in active workspace. Got: {active_tab_text}"

