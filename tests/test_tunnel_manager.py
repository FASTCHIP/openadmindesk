"""Tests for tunnel manager — behavioral."""

from __future__ import annotations

from openadmindesk.core.tunnel_profile import TunnelProfile, TunnelType
from openadmindesk.core import tunnel_manager
from openadmindesk.core.tunnel_manager import TunnelManager, TunnelProcess


def test_tunnel_manager_creation() -> None:
    """Tunnel manager creates in empty state."""
    manager = TunnelManager()
    assert manager is not None


def test_tunnel_manager_start_stop_without_ssh() -> None:
    """Starting tunnel should not crash (may succeed if SSH is available)."""
    manager = TunnelManager()
    profile = TunnelProfile(
        name="Test Tunnel",
        host="localhost",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
    )
    result = manager.start_tunnel(profile)
    # Should not raise an exception — result depends on SSH availability
    assert isinstance(result, bool)


def test_tunnel_manager_stop_nonexistent() -> None:
    """Stopping a nonexistent tunnel should not raise."""
    manager = TunnelManager()
    manager.stop_tunnel("nonexistent-id")  # Should not raise


def test_tunnel_manager_status_nonexistent() -> None:
    """Getting status of nonexistent tunnel returns None."""
    manager = TunnelManager()
    status = manager.get_tunnel_status("nonexistent-id")
    assert status is None

def test_tunnel_process_captures_stderr(monkeypatch) -> None:
    """Tunnel status should expose captured SSH stderr diagnostics."""
    captured = {}

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = ["bind failed\n"]

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(tunnel_manager.subprocess, "Popen", fake_popen)
    profile = TunnelProfile(
        name="Test Tunnel",
        host="example.com",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
    )

    process = TunnelProcess(profile)
    assert process.start()
    process._stderr_thread.join(timeout=1)

    status = process.get_status()
    assert captured["kwargs"]["stderr"] == tunnel_manager.subprocess.PIPE
    assert status["last_error"] == "bind failed"
