"""Tests for GUI launcher."""

from openadmindesk.core.gui_launcher import GuiLauncher
from openadmindesk.core.tunnel_profile import TunnelProfile


def test_gui_launcher_builds_safe_ssh_command(monkeypatch) -> None:
    launched = []

    class FakeProcess:
        pass

    def fake_popen(cmd, **kwargs):
        launched.append((cmd, kwargs))
        return FakeProcess()

    launcher = GuiLauncher()
    monkeypatch.setattr(launcher.x11_detector, "is_x11_available", lambda: True)
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    profile = TunnelProfile(name="gui", host="example.com", username="admin")

    assert launcher.launch_gui_app(profile, "xterm") is True

    cmd, kwargs = launched[0]
    assert cmd[0] == "ssh"
    assert "-X" in cmd
    assert "-Y" in cmd
    assert "admin@example.com" in cmd
    assert cmd[-2:] == ["--", "xterm"]
    assert kwargs["shell"] is False


def test_gui_launcher_rejects_unsafe_host() -> None:
    launcher = GuiLauncher()
    profile = TunnelProfile(name="bad", host="host;rm -rf /", username="admin")

    assert launcher.launch_gui_app(profile, "xterm") is False
