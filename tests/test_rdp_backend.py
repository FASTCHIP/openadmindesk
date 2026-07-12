"""Tests for RDP backend cross-platform detection and command safety."""

from __future__ import annotations

from openadmindesk.core import rdp_backend
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.rdp_backend import RdpBackend


def test_rdp_backend_creation() -> None:
    profile = Profile(
        name="Test RDP",
        host="192.168.1.1",
        port=3389,
        session_type=SessionType.RDP,
    )
    backend = RdpBackend(profile)
    assert backend is not None
    assert backend.profile.host == "192.168.1.1"


def test_rdp_backend_is_available() -> None:
    """is_available() should return bool — True if xfreerdp/mstsc found."""
    result = RdpBackend.is_available()
    assert isinstance(result, bool)


def test_rdp_backend_not_connected_initially() -> None:
    profile = Profile(
        name="Test",
        host="localhost",
        port=3389,
        session_type=SessionType.RDP,
    )
    backend = RdpBackend(profile)
    assert backend.is_connected() is False


def test_linux_command_does_not_include_plaintext_passwords(monkeypatch) -> None:
    monkeypatch.setattr(rdp_backend, "find_rdp_binary", lambda: "xfreerdp")
    profile = Profile(
        name="RDP Secret",
        host="rdp.example.com",
        port=3390,
        username="alice",
        password="plain-password",
        session_type=SessionType.RDP,
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
        rdp_gateway_password="gateway-secret",
    )

    cmd = RdpBackend(profile)._build_linux_command()
    command_text = " ".join(cmd)

    assert "/v:rdp.example.com:3390" in cmd
    assert "/u:alice" in cmd
    assert "/g:gw.example.com" in cmd
    assert "/gu:gw-user" in cmd
    assert "/cert:tofu" in cmd
    assert "/cert:ignore" not in cmd
    assert "plain-password" not in command_text
    assert "gateway-secret" not in command_text
    assert not any(arg.startswith("/p:") for arg in cmd)
    assert not any(arg.startswith("/gp:") for arg in cmd)

def test_rdp_linux_connect_captures_stderr(monkeypatch) -> None:
    """Linux RDP launches should keep stderr for diagnostics."""
    captured = {}

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = ["rdp failed\n"]

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(rdp_backend, "find_rdp_binary", lambda: "xfreerdp")
    monkeypatch.setattr(rdp_backend, "is_windows", lambda: False)
    monkeypatch.setattr(rdp_backend.subprocess, "Popen", fake_popen)

    backend = RdpBackend(Profile(name="RDP", host="example.com", session_type=SessionType.RDP))
    assert backend.connect()

    assert captured["kwargs"]["stderr"] == rdp_backend.subprocess.PIPE
    assert captured["kwargs"]["stdout"] == rdp_backend.subprocess.DEVNULL
    backend._stderr_thread.join(timeout=1)
    assert backend.last_error() == "rdp failed"
