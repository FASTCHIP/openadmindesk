"""Tests for tabbed workspace."""

from PySide6.QtWidgets import QTabBar

from openadmindesk.core.profile import Profile
from openadmindesk.ui.sftp_file_browser import SftpFileBrowser
from openadmindesk.ui.tabbed_workspace import TabbedWorkspace
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab


def test_tabbed_workspace_creation() -> None:
    """Tabbed workspace starts with a home tab."""
    workspace = TabbedWorkspace()

    assert workspace.count() == 1
    assert "Home" in workspace.tabText(0)


def test_add_ssh_terminal_tab() -> None:
    """Adding an SSH terminal creates a real SSH tab and selects it."""
    workspace = TabbedWorkspace()
    profile = Profile(name="Test Server", host="example.com", port=22, username="user")

    workspace.add_ssh_terminal_tab(profile)

    assert workspace.count() == 2
    assert isinstance(workspace.currentWidget(), SshTerminalTab)
    assert "Test Server" in workspace.tabText(workspace.currentIndex())
    assert not workspace.tabIcon(workspace.currentIndex()).isNull()
    assert workspace.tabBar().tabButton(workspace.currentIndex(), QTabBar.RightSide) is not None


def test_sftp_request_opens_dedicated_file_browser_tab(monkeypatch) -> None:
    monkeypatch.setattr(SftpFileBrowser, "_connect_to_sftp", lambda self: None)
    workspace = TabbedWorkspace()
    profile = Profile(name="Test Server", host="example.com", port=22, username="user")
    workspace.add_ssh_terminal_tab(profile)
    ssh_tab = workspace.currentWidget()

    ssh_tab.sftp_requested.emit(profile)

    assert workspace.count() == 3
    assert isinstance(workspace.currentWidget(), SftpFileBrowser)
    assert "SFTP Test Server" in workspace.tabText(workspace.currentIndex())
    assert not workspace.tabIcon(workspace.currentIndex()).isNull()

    ssh_tab.sftp_requested.emit(profile)

    assert workspace.count() == 3
    assert isinstance(workspace.currentWidget(), SftpFileBrowser)


def test_visible_tab_close_button_closes_current_tab() -> None:
    workspace = TabbedWorkspace()
    profile = Profile(name="Close Me", host="example.com", port=22, username="user")
    workspace.add_ssh_terminal_tab(profile)
    index = workspace.currentIndex()
    button = workspace.tabBar().tabButton(index, QTabBar.RightSide)

    assert button is not None

    button.click()

    assert workspace.count() == 1
