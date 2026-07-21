"""Tests for connection runtime UX and vault integration."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from unittest.mock import patch

from openadmindesk.core.account import Account
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.ui.main_window import MainWindow
from openadmindesk.ui.rdp_session_tab import RdpSessionTab

pytestmark = pytest.mark.qt


def _new_window(tmp_path, monkeypatch) -> MainWindow:
    """Helper to create a MainWindow with temporary storage and no startup timers."""
    monkeypatch.setattr(
        "openadmindesk.ui.main_window.default_db_path",
        lambda: str(tmp_path / "profiles.db"),
    )
    monkeypatch.setattr(
        "openadmindesk.ui.main_window.default_vault_path",
        lambda: str(tmp_path / "vault.json"),
    )
    monkeypatch.setattr(
        "PySide6.QtCore.QTimer.singleShot", lambda *args, **kwargs: None
    )
    window = MainWindow()
    window._vault_lock_timer.stop()
    window._multi_exec_timer.stop()
    return window


def test_vault_locked_decline(tmp_path, monkeypatch):
    """Test 1: Locked vault decline returns deep copy, original/runtime password None, event mentions vault locked."""
    window = _new_window(tmp_path, monkeypatch)

    class FakeLockedVault:
        def is_unlocked(self):
            return False

        def get_account(self, cid):
            return None

    window.vault_manager = FakeLockedVault()

    messages = []

    def mock_show_message(msg, *args):
        messages.append(msg)

    monkeypatch.setattr(window.connection_event_area, "showMessage", mock_show_message)

    with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.No):
        profile = Profile(name="Test", host="1.2.3.4", credential_id="cred1")
        runtime_profile = window._prepare_profile_for_connection(profile)

        assert runtime_profile is not profile
        assert runtime_profile.password is None
        assert profile.password is None
        assert len(messages) == 1
        assert "vault is locked" in messages[0]

    window.deleteLater()


def test_unlock_hydrate(tmp_path, monkeypatch):
    """Test 2: Unlock hydrates runtime copy: mutable fake vault get_account Account username/password;
    QMessageBox Yes; window._unlock_vault sets fake unlocked; original remains secret-free, runtime credentials hydrated."""
    window = _new_window(tmp_path, monkeypatch)

    class FakeVault:
        def __init__(self):
            self.unlocked = False

        def is_unlocked(self):
            return self.unlocked

        def get_account(self, cid):
            return (
                Account(username="vault_user", password="vault_pass")
                if self.unlocked
                else None
            )

    vault = FakeVault()
    window.vault_manager = vault

    def mock_unlock():
        vault.unlocked = True

    monkeypatch.setattr(window, "_unlock_vault", mock_unlock)

    with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
        profile = Profile(name="Test", host="1.2.3.4", credential_id="cred1")
        runtime_profile = window._prepare_profile_for_connection(profile)

        assert vault.unlocked is True
        assert runtime_profile.username == "vault_user"
        assert runtime_profile.password == "vault_pass"
        assert profile.password is None

    window.deleteLater()


def test_saved_ssh_visibility(tmp_path, monkeypatch):
    """Test 3: Saved SSH visibility: use helper's real temporary ProfileStore; save profile;
    set real filter nonmatch; call _on_profile_saved; assert filter empty, recursive exact tree find finds profile, event contains name."""
    window = _new_window(tmp_path, monkeypatch)

    profile = Profile(name="VisibleSSH", host="1.2.3.4", session_type=SessionType.SSH)
    window.profile_store.save_profile(profile)

    window.connection_tree.filter_input.setText("ZZZ_NON_MATCH")

    messages = []

    def mock_show_message(msg, *args):
        messages.append(msg)

    monkeypatch.setattr(window.connection_event_area, "showMessage", mock_show_message)

    window._on_profile_saved(profile.name)

    assert window.connection_tree.filter_input.text() == ""
    items = window.connection_tree._tree.findItems(
        profile.name, Qt.MatchExactly | Qt.MatchRecursive, 0
    )
    assert len(items) > 0
    assert any(profile.name in msg for msg in messages)

    window.deleteLater()


def test_one_time_rdp(monkeypatch):
    """Test 4: RDP one-time password: profile RDP username no password; QInputDialog secret;
    spy client connect; assert once/password/status Connecting."""
    profile = Profile(
        name="RDP_Test",
        host="1.2.3.4",
        username="admin",
        password=None,
        session_type=SessionType.RDP,
    )
    tab = RdpSessionTab(profile)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *args, **kwargs: ("secret123", True),
    )

    calls = []

    def mock_connect(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(tab._client, "connect_to_host", mock_connect)

    tab._connect()

    assert profile.password == "secret123"
    assert len(calls) == 1
    assert tab._status_label.text() == "● Connecting..."

    tab.deleteLater()


def test_rdp_cancel(monkeypatch):
    """Test 5: RDP password cancel: no connect, connected false, button Connect enabled,
    label Password required, signal actionable."""
    profile = Profile(
        name="RDP_Cancel",
        host="1.2.3.4",
        username="admin",
        password=None,
        session_type=SessionType.RDP,
    )
    tab = RdpSessionTab(profile)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText", lambda *args, **kwargs: ("", False)
    )

    calls = []

    def mock_connect(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(tab._client, "connect_to_host", mock_connect)

    emitted = []
    tab.status_message.connect(lambda msg: emitted.append(msg))

    tab._connect()

    assert len(calls) == 0
    assert tab._connected is False
    assert tab._connect_button.text() == "Connect"
    assert tab._connect_button.isEnabled()
    assert tab._status_label.text() == "● Password required"
    assert len(emitted) > 0
    assert any("password" in msg.lower() for msg in emitted)

    tab.deleteLater()


def test_rdp_error(monkeypatch):
    """Test 6: RDP error: start connected true/CAD enabled if useful;
    _on_error("NLA authentication failed"); exact explicit error label, full tooltip/signal,
    connected false, connect button reset/enabled, CAD disabled."""
    profile = Profile(name="RDP_Error", host="1.2.3.4", session_type=SessionType.RDP)
    tab = RdpSessionTab(profile)

    tab._connected = True
    tab._cad_button.setEnabled(True)

    emitted = []
    tab.status_message.connect(lambda msg: emitted.append(msg))

    tab._on_error("NLA authentication failed")

    assert tab._status_label.text() == "● Error: NLA authentication failed"
    assert tab._status_label.toolTip() == "NLA authentication failed"
    assert "RDP connection failed: NLA authentication failed" in emitted
    assert tab._connected is False
    assert tab._connect_button.text() == "Connect"
    assert tab._connect_button.isEnabled()
    assert not tab._cad_button.isEnabled()

    tab.deleteLater()
