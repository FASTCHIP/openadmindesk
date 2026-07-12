"""Tests for attached SFTP side browser functionality."""

from unittest.mock import patch
from PySide6.QtWidgets import QWidget
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab
from openadmindesk.core.profile import Profile


class _FakeSftpBrowser(QWidget):
    """A minimal QWidget stand-in for SftpFileBrowser in tests."""

    def __init__(self, profile) -> None:
        super().__init__()
        self.profile = profile
        self._current_path = "/"

    def disconnect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def deleteLater(self) -> None:
        super().deleteLater()

    def _navigate_to(self, path: str) -> None:
        self._current_path = path


def test_ssh_terminal_tab_has_attached_sftp_methods() -> None:
    """SSH terminal tab has attached SFTP methods."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Check methods exist
    assert hasattr(tab, "has_attached_sftp")
    assert hasattr(tab, "open_attached_sftp")
    assert hasattr(tab, "close_attached_sftp")
    assert hasattr(tab, "detach_attached_sftp")
    
    # Check initial state
    assert tab.has_attached_sftp() is False


def test_ssh_terminal_tab_attached_sftp_buttons_exist() -> None:
    """SSH terminal tab has attached SFTP buttons."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Check buttons exist
    assert hasattr(tab, "sftp_attach_btn")
    assert hasattr(tab, "sftp_detach_btn")
    assert hasattr(tab, "sftp_close_btn")
    
    # Check initial state
    assert tab.sftp_attach_btn.isEnabled() is False
    assert tab.sftp_detach_btn.isEnabled() is False
    assert tab.sftp_close_btn.isEnabled() is False


def test_ssh_terminal_tab_attached_sftp_buttons_enabled_on_connect() -> None:
    """Attached SFTP buttons are enabled when SSH connection is established."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Simulate successful connection
    tab._connected = True
    tab._on_connect_finished(True, "")
    
    # Check that SFTP attach button is enabled
    assert tab.sftp_attach_btn.isEnabled() is True
    assert tab.sftp_detach_btn.isEnabled() is False
    assert tab.sftp_close_btn.isEnabled() is False


def test_ssh_terminal_tab_attached_sftp_buttons_disabled_on_disconnect() -> None:
    """Attached SFTP buttons are disabled when SSH connection is closed."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Set up as connected
    tab._connected = True
    tab.sftp_attach_btn.setEnabled(True)
    
    # Disconnect
    tab._disconnect()
    
    # Check buttons are disabled
    assert tab.sftp_attach_btn.isEnabled() is False
    assert tab.sftp_detach_btn.isEnabled() is False
    assert tab.sftp_close_btn.isEnabled() is False


def test_ssh_terminal_tab_open_attached_sftp_creates_browser() -> None:
    """Opening attached SFTP creates an SFTP browser."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Set up as connected
    tab._connected = True
    
    # Mock SftpFileBrowser with a fake QWidget-based browser
    with patch('openadmindesk.ui.ssh_terminal_tab.SftpFileBrowser') as mock_browser:
        fake_browser = _FakeSftpBrowser(profile)
        mock_browser.return_value = fake_browser
        
        # Open attached SFTP
        tab.open_attached_sftp()
        
        # Check browser was created
        mock_browser.assert_called_once_with(profile)
        assert tab.has_attached_sftp() is True
        assert tab._attached_sftp_browser is fake_browser
        
        # Check buttons state
        assert tab.sftp_attach_btn.isEnabled() is False
        assert tab.sftp_detach_btn.isEnabled() is True
        assert tab.sftp_close_btn.isEnabled() is True


def test_ssh_terminal_tab_close_attached_sftp_removes_browser() -> None:
    """Closing attached SFTP removes the browser."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Set up as connected
    tab._connected = True
    
    # Mock SftpFileBrowser with a fake QWidget-based browser
    with patch('openadmindesk.ui.ssh_terminal_tab.SftpFileBrowser') as mock_browser:
        fake_browser = _FakeSftpBrowser(profile)
        mock_browser.return_value = fake_browser
        
        # Open attached SFTP
        tab.open_attached_sftp()
        assert tab.has_attached_sftp() is True
        assert tab._attached_sftp_browser is fake_browser
        
        # Close attached SFTP
        tab.close_attached_sftp()
        
        # Check browser was removed
        assert tab.has_attached_sftp() is False
        
        # Check buttons state
        assert tab.sftp_attach_btn.isEnabled() is True
        assert tab.sftp_detach_btn.isEnabled() is False
        assert tab.sftp_close_btn.isEnabled() is False


def test_ssh_terminal_tab_detach_attached_sftp_emits_signal() -> None:
    """Detaching attached SFTP emits the sftp_requested signal."""
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    
    # Set up as connected
    tab._connected = True
    
    # Mock SftpFileBrowser with a fake QWidget-based browser
    with patch('openadmindesk.ui.ssh_terminal_tab.SftpFileBrowser') as mock_browser:
        fake_browser = _FakeSftpBrowser(profile)
        mock_browser.return_value = fake_browser
        
        # Open attached SFTP
        tab.open_attached_sftp()
        assert tab.has_attached_sftp() is True
        
        # Mock the signal
        with patch.object(tab, 'sftp_requested') as mock_signal:
            # Detach attached SFTP
            tab.detach_attached_sftp()
            
            # Check signal was emitted
            mock_signal.emit.assert_called_once_with(profile)
            
            # Check browser was closed
            assert tab.has_attached_sftp() is False