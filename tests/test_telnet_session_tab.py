"""Tests for TelnetSessionTab with cleartext warning functionality."""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QMessageBox

from openadmindesk.ui.telnet_session_tab import TelnetSessionTab
from openadmindesk.core.profile import SessionType


@pytest.fixture
def mock_profile():
    profile = MagicMock()
    profile.name = "Legacy"
    profile.host = "legacy.example"
    profile.port = 23
    profile.username = "admin"
    profile.session_type = SessionType.TELNET
    return profile


@pytest.fixture
def telnet_tab(mock_profile):
    return TelnetSessionTab(mock_profile)


def test_confirm_cleartext_dialog_shows_correct_title_and_body(telnet_tab):
    """Test that the warning dialog shows correct title and body."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.No
        result = telnet_tab._confirm_cleartext_connection()
        assert result is False
        mock_warning.assert_called_once_with(
            telnet_tab,
            "Telnet Connection Warning",
            "This connection uses the Telnet protocol, which transmits credentials and session data in plaintext over the network. Network observers can read your username, password, and all session data. Only use this connection type for trusted legacy systems.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )


def test_initial_connect_no_cancels(telnet_tab):
    """Test that initial connect with 'No' cancels connection."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.No
        # Mock backend connect to avoid actual connection
        with patch.object(telnet_tab.backend, 'connect', return_value=True) as mock_connect:
            # Call _connect directly to test the warning flow
            telnet_tab._connect()
            # Should not call backend connect
            mock_connect.assert_not_called()


def test_initial_connect_yes_starts_connection(telnet_tab):
    """Test that initial connect with 'Yes' starts connection."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.Yes
        # Mock backend connect to avoid actual connection
        with patch.object(telnet_tab.backend, 'connect', return_value=True) as mock_connect:
            with patch('PySide6.QtCore.QTimer.singleShot', side_effect=lambda _delay, callback: callback()):
                # Call _connect directly to test the warning flow
                telnet_tab._connect()
                # Should call backend connect
                mock_connect.assert_called_once()


def test_reconnect_no_preserves_connection(telnet_tab):
    """Test that reconnect with 'No' preserves connection."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.No
        # Mock backend disconnect to avoid actual disconnection
        with patch.object(telnet_tab.backend, 'disconnect') as mock_disconnect:
            # Call _on_reconnect directly to test the warning flow
            telnet_tab._on_reconnect()
            # Should not call backend disconnect
            mock_disconnect.assert_not_called()


def test_reconnect_yes_disconnects_and_starts(telnet_tab):
    """Test that reconnect with 'Yes' disconnects and starts connection."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.Yes
        # Mock backend disconnect and connect to avoid actual operations
        with patch.object(telnet_tab.backend, 'disconnect') as mock_disconnect:
            with patch.object(telnet_tab.backend, 'connect', return_value=True) as mock_connect:
                with patch('PySide6.QtCore.QTimer.singleShot', side_effect=lambda _delay, callback: callback()):
                    # Call _on_reconnect directly to test the warning flow
                    telnet_tab._on_reconnect()
                    # Should call backend disconnect
                    mock_disconnect.assert_called_once()
                    # Should call backend connect
                    mock_connect.assert_called_once()


def test_dialog_exception_returns_false(telnet_tab):
    """Test that dialog exception returns False (fail closed)."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.side_effect = Exception("Dialog failed")
        result = telnet_tab._confirm_cleartext_connection()
        assert result is False


def test_confirm_cleartext_connection_returns_bool(telnet_tab):
    """Test that _confirm_cleartext_connection returns boolean."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.Yes
        result = telnet_tab._confirm_cleartext_connection()
        assert isinstance(result, bool)
        assert result is True


def test_confirm_cleartext_connection_returns_false_on_no(telnet_tab):
    """Test that _confirm_cleartext_connection returns False on No."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.return_value = QMessageBox.No
        result = telnet_tab._confirm_cleartext_connection()
        assert isinstance(result, bool)
        assert result is False


def test_confirm_cleartext_connection_returns_false_on_exception(telnet_tab):
    """Test that _confirm_cleartext_connection returns False on exception."""
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        mock_warning.side_effect = Exception("Dialog failed")
        result = telnet_tab._confirm_cleartext_connection()
        assert isinstance(result, bool)
        assert result is False


def test_start_connection_executes_immediately(telnet_tab):
    """Test that _start_connection executes immediately with QTimer.singleShot."""
    with patch('PySide6.QtCore.QTimer.singleShot') as mock_single_shot:
        # Mock backend connect to avoid actual connection
        with patch.object(telnet_tab.backend, 'connect', return_value=True) as mock_connect:
            telnet_tab._start_connection()
            # Should call QTimer.singleShot with callback
            mock_single_shot.assert_called_once()
            # Callback should be called immediately
            callback = mock_single_shot.call_args[0][1]
            # Call the callback to test it works
            callback()
            # Backend connect should be called
            assert mock_connect.called


def test_connect_calls_confirm_and_start(telnet_tab):
    """Test that _connect calls confirmation and then starts connection."""
    with patch.object(telnet_tab, '_confirm_cleartext_connection') as mock_confirm:
        with patch.object(telnet_tab, '_start_connection') as mock_start:
            mock_confirm.return_value = True
            telnet_tab._connect()
            mock_confirm.assert_called_once()
            mock_start.assert_called_once()


def test_connect_cancelled_does_not_start(telnet_tab):
    """Test that _connect does not start connection when cancelled."""
    with patch.object(telnet_tab, '_confirm_cleartext_connection') as mock_confirm:
        with patch.object(telnet_tab, '_start_connection') as mock_start:
            mock_confirm.return_value = False
            telnet_tab._connect()
            mock_confirm.assert_called_once()
            mock_start.assert_not_called()


def test_on_reconnect_calls_confirm_disconnect_and_start(telnet_tab):
    """Test that _on_reconnect calls confirmation, disconnects, and starts connection."""
    with patch.object(telnet_tab, '_confirm_cleartext_connection') as mock_confirm:
        with patch.object(telnet_tab, '_disconnect') as mock_disconnect:
            with patch.object(telnet_tab, '_start_connection') as mock_start:
                mock_confirm.return_value = True
                telnet_tab._on_reconnect()
                mock_confirm.assert_called_once()
                mock_disconnect.assert_called_once()
                mock_start.assert_called_once()


def test_on_reconnect_cancelled_does_not_disconnect_or_start(telnet_tab):
    """Test that _on_reconnect does not disconnect or start when cancelled."""
    with patch.object(telnet_tab, '_confirm_cleartext_connection') as mock_confirm:
        with patch.object(telnet_tab, '_disconnect') as mock_disconnect:
            with patch.object(telnet_tab, '_start_connection') as mock_start:
                mock_confirm.return_value = False
                telnet_tab._on_reconnect()
                mock_confirm.assert_called_once()
                mock_disconnect.assert_not_called()
                mock_start.assert_not_called()