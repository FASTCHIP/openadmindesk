"""Tests for main window with activity rail and workspace layout."""

from unittest.mock import patch

from openadmindesk.ui.activity_rail import ActivityRail
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


def test_main_window_has_activity_rail() -> None:
    window = _window()

    assert isinstance(window.activity_rail, ActivityRail)
    assert window.activity_rail.minimumWidth() == 280
    assert window.activity_rail.maximumWidth() == 350


def test_main_window_has_view_toolbar() -> None:
    window = _window()

    assert window.view_toolbar is not None
    assert window.split_single_btn is not None
    assert window.split_horizontal_btn is not None
    assert window.split_vertical_btn is not None
    assert window.split_grid_btn is not None


def test_main_window_initial_layout() -> None:
    window = _window()

    assert window.workspace_layout == "single"
    assert window.split_single_btn.isChecked()


def test_main_window_workspace_layout_switching() -> None:
    window = _window()

    window._set_workspace_layout("single")
    assert window.workspace_layout == "single"
    assert window.split_single_btn.isChecked()

    window._set_workspace_layout("horizontal")
    assert window.workspace_layout == "horizontal"
    assert window.split_horizontal_btn.isChecked()

    window._set_workspace_layout("vertical")
    assert window.workspace_layout == "vertical"
    assert window.split_vertical_btn.isChecked()

    window._set_workspace_layout("grid")
    assert window.workspace_layout == "grid"
    assert window.split_grid_btn.isChecked()


def test_main_window_activity_mode_changes() -> None:
    window = _window()

    with patch.object(window.connection_event_area, 'showMessage') as mock_show:
        window._on_activity_mode_changed("sftp")
        mock_show.assert_called_with("Mode: sftp", 3000)

        window._on_activity_mode_changed("tunnels")
        mock_show.assert_called_with("Mode: tunnels", 3000)


def test_main_window_sessions_widget_in_rail() -> None:
    window = _window()

    sessions_widget = window.activity_rail.mode_widgets.get("sessions")
    assert sessions_widget is window.connection_tree


def test_main_window_central_widget_layout() -> None:
    window = _window()

    central_widget = window.centralWidget()
    assert central_widget is not None
    layout = central_widget.layout()
    assert layout is not None
    assert layout.count() == 2
    assert layout.itemAt(0).widget() is window.activity_rail
    assert layout.itemAt(1).widget() is window.workspace_container
