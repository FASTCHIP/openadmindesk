"""Tests for SSH terminal tab."""

from dataclasses import dataclass

from openadmindesk.core.profile import Profile
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab


@dataclass
class FakeHostKeyPrompt:
    hostname: str = "example.com"
    key_type: str = "ssh-rsa"
    fingerprint_sha256: str = "SHA256:test"


class FakeBackend:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.disconnect_calls = 0
        self.trust_calls = 0
        self.pending_prompt = None

    def send(self, text: str) -> None:
        self.sent.append(text)

    def disconnect(self) -> None:
        self.disconnect_calls += 1

    def pending_host_key(self):
        return self.pending_prompt

    def trust_pending_host_key(self) -> bool:
        self.trust_calls += 1
        if not self.pending_prompt:
            return False
        self.pending_prompt = None
        return True


class FakeWorker:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1


def _profile() -> Profile:
    return Profile(
        name="Test Server",
        host="example.com",
        port=22,
        username="user",
    )


def test_ssh_terminal_tab_creation() -> None:
    """SSH terminal tab keeps the profile and starts disconnected."""
    profile = _profile()
    tab = SshTerminalTab(profile)

    assert tab.profile == profile
    assert not tab._connected
    assert not tab.sftp_button.isEnabled()
    assert tab._connect_thread is None
    assert tab.focusProxy() is tab.terminal


def test_backend_output_is_fed_on_ui_slot(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    seen: list[str] = []
    monkeypatch.setattr(tab.terminal, "feed", seen.append)

    tab._on_backend_output("привет".encode())

    assert seen == ["привет"]


def test_connect_success_updates_controls() -> None:
    tab = SshTerminalTab(_profile())

    tab._on_connect_finished(True, "")

    assert tab._connected
    assert tab.connect_button.text() == "Disconnect"
    assert tab.reconnect_button.isEnabled()
    assert tab.sftp_button.isEnabled()
    assert tab.snippet_button.isEnabled()


def test_connect_success_focuses_terminal_and_wakes_prompt(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    backend = FakeBackend()
    tab.backend = backend  # type: ignore[assignment]
    focused = []
    monkeypatch.setattr(tab.terminal, "setFocus", lambda *args: focused.append(args))
    monkeypatch.setattr(
        "openadmindesk.ui.ssh_terminal_tab.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )

    tab._on_connect_finished(True, "")

    assert focused
    assert backend.sent == ["\r"]


def test_connect_failure_reports_backend_error(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    seen: list[str] = []
    monkeypatch.setattr(tab.terminal, "feed", seen.append)

    tab._on_connect_finished(False, "host key rejected")

    assert not tab._connected
    assert tab.connect_button.text() == "Connect"
    assert "Connection Failed" in tab.status_label.text()
    assert seen == ["\r\n*** host key rejected ***\r\n"]


def test_pending_host_key_enables_trust_flow(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    backend = FakeBackend()
    backend.pending_prompt = FakeHostKeyPrompt()
    tab.backend = backend  # type: ignore[assignment]
    seen: list[str] = []
    reconnects = []
    monkeypatch.setattr(tab.terminal, "feed", seen.append)
    monkeypatch.setattr(tab, "_confirm_trust_host_key", lambda prompt: False)
    monkeypatch.setattr(tab, "_connect", lambda: reconnects.append(True))

    tab._on_connect_finished(False, "unknown host key")

    assert tab.trust_host_button.isEnabled()
    assert "SHA256:test" in seen[-1]

    tab._trust_pending_host_key(auto_reconnect=False)

    assert backend.trust_calls == 1
    assert not tab.trust_host_button.isEnabled()
    assert "Host Key Trusted" in tab.status_label.text()
    assert reconnects == []


def test_cancel_connect_cancels_worker_and_resets_ui() -> None:
    tab = SshTerminalTab(_profile())
    worker = FakeWorker()
    backend = FakeBackend()
    tab._connect_worker = worker  # type: ignore[assignment]
    tab.backend = backend  # type: ignore[assignment]
    tab.connect_button.setText("Cancel")

    tab._cancel_connect()

    assert worker.cancel_calls == 1
    assert backend.disconnect_calls == 1
    assert not tab._connected
    assert tab.connect_button.text() == "Connect"
    assert "Disconnected" in tab.status_label.text()


def test_key_pressed_sends_to_backend_and_records_macro() -> None:
    tab = SshTerminalTab(_profile())
    backend = FakeBackend()
    tab.backend = backend  # type: ignore[assignment]
    tab._macro_recording = True

    tab._on_key_pressed("ls\r")

    assert backend.sent == ["ls\r"]
    assert tab._macro_keys == ["ls\r"]


def test_disconnect_closes_backend_and_disables_dependent_actions() -> None:
    tab = SshTerminalTab(_profile())
    backend = FakeBackend()
    tab.backend = backend  # type: ignore[assignment]
    tab._connected = True
    tab.sftp_button.setEnabled(True)
    tab.snippet_button.setEnabled(True)
    tab.monitor_btn.setEnabled(True)

    tab._disconnect()

    assert backend.disconnect_calls == 1
    assert not tab._connected
    assert not tab.sftp_button.isEnabled()
    assert not tab.snippet_button.isEnabled()
    assert not tab.monitor_btn.isEnabled()

def test_connect_prompts_for_password_when_profile_has_no_auth(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    started = []
    monkeypatch.setattr(
        "openadmindesk.ui.ssh_terminal_tab.QInputDialog.getText",
        lambda *args, **kwargs: ("prompt-secret", True),
    )
    monkeypatch.setattr(tab, "_connect", lambda: started.append(True))

    assert tab._ensure_auth_material()
    assert tab.profile.password == "prompt-secret"


def test_connect_prompt_cancel_stops_connection(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    monkeypatch.setattr(
        "openadmindesk.ui.ssh_terminal_tab.QInputDialog.getText",
        lambda *args, **kwargs: ("", False),
    )

    assert not tab._ensure_auth_material()
    assert tab.profile.password is None


def test_connect_does_not_prompt_when_private_key_is_explicit(monkeypatch) -> None:
    profile = _profile()
    profile.private_key_path = "/tmp/id_ed25519"
    tab = SshTerminalTab(profile)
    prompted = []
    monkeypatch.setattr(
        "openadmindesk.ui.ssh_terminal_tab.QInputDialog.getText",
        lambda *args, **kwargs: prompted.append(True),
    )

    assert tab._ensure_auth_material()
    assert prompted == []

def test_pending_host_key_confirm_yes_trusts_and_reconnects(monkeypatch) -> None:
    tab = SshTerminalTab(_profile())
    backend = FakeBackend()
    backend.pending_prompt = FakeHostKeyPrompt()
    tab.backend = backend  # type: ignore[assignment]
    reconnects = []
    monkeypatch.setattr(tab, "_confirm_trust_host_key", lambda prompt: True)
    monkeypatch.setattr(tab, "_connect", lambda: reconnects.append(True))
    monkeypatch.setattr(
        "openadmindesk.ui.ssh_terminal_tab.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )

    tab._on_connect_finished(False, "unknown host key")

    assert backend.trust_calls == 1
    assert not tab.trust_host_button.isEnabled()
    assert reconnects == [True]
