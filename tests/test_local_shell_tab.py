"""Tests for local shell terminal tab."""

from openadmindesk.ui.local_shell_tab import LocalShellTab


class FakeBackend:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.disconnect_calls = 0

    def send(self, text: str) -> None:
        self.sent.append(text)

    def disconnect(self) -> None:
        self.disconnect_calls += 1


class FakeWorker:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1


def _tab(monkeypatch) -> LocalShellTab:
    monkeypatch.setattr(LocalShellTab, "_connect", lambda self: None)
    return LocalShellTab("test-shell")


def test_local_shell_output_slot_feeds_terminal(monkeypatch) -> None:
    tab = _tab(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(tab.terminal, "feed", seen.append)
    monkeypatch.setattr(tab.terminal, "_reset_scroll_position", lambda: seen.append("reset"))

    tab._on_backend_output("hello")

    assert seen == ["hello", "reset"]


def test_local_shell_connect_success_updates_controls(monkeypatch) -> None:
    tab = _tab(monkeypatch)

    tab._on_connect_finished(True)

    assert tab._connected
    assert "Connected" in tab.status_label.text()
    assert tab.reconnect_button.isEnabled()


def test_local_shell_connect_failure_updates_controls(monkeypatch) -> None:
    tab = _tab(monkeypatch)

    tab._on_connect_finished(False)

    assert not tab._connected
    assert "Connection Failed" in tab.status_label.text()
    assert not tab.reconnect_button.isEnabled()


def test_local_shell_keypress_and_reconnect_use_backend(monkeypatch) -> None:
    tab = _tab(monkeypatch)
    backend = FakeBackend()
    reconnects = []
    tab.backend = backend  # type: ignore[assignment]
    monkeypatch.setattr(tab, "_connect", lambda: reconnects.append("connect"))

    tab._on_key_pressed("pwd\r")
    tab._on_reconnect()

    assert backend.sent == ["pwd\r"]
    assert backend.disconnect_calls == 1
    assert reconnects == ["connect"]
    assert not tab._connected


def test_local_shell_stop_connect_worker_cancels_worker(monkeypatch) -> None:
    tab = _tab(monkeypatch)
    worker = FakeWorker()
    backend = FakeBackend()
    tab._connect_worker = worker  # type: ignore[assignment]
    tab.backend = backend  # type: ignore[assignment]
    tab._connect_thread = None

    tab._stop_connect_worker()

    assert worker.cancel_calls == 0
    assert backend.disconnect_calls == 0
