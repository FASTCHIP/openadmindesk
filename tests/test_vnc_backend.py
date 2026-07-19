"""Tests for VNC backend process diagnostics."""

from __future__ import annotations

from openadmindesk.core import vnc_backend
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.vnc_backend import VncBackend


def test_vnc_backend_not_connected_initially(monkeypatch) -> None:
    monkeypatch.setattr(vnc_backend, "_find_vnc_viewer", lambda: "vncviewer")
    backend = VncBackend(Profile(name="VNC", host="example.com", session_type=SessionType.VNC))

    assert backend.is_connected() is False


def test_vnc_connect_captures_stderr(monkeypatch) -> None:
    """VNC launches should keep stderr for diagnostics."""
    captured = {}

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = ["vnc failed\n"]

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(vnc_backend, "_find_vnc_viewer", lambda: "vncviewer")
    monkeypatch.setattr(vnc_backend.subprocess, "Popen", fake_popen)

    backend = VncBackend(Profile(name="VNC", host="example.com", session_type=SessionType.VNC))
    assert backend.connect()

    assert captured["cmd"][0] == "vncviewer"
    assert "example.com" in captured["cmd"][-1]
    assert captured["kwargs"]["stderr"] == vnc_backend.subprocess.PIPE
    assert captured["kwargs"]["stdout"] == vnc_backend.subprocess.DEVNULL
    backend._stderr_thread.join(timeout=1)
    assert backend.last_error() == "vnc failed"
