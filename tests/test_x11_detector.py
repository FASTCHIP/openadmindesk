"""Tests for X11 detector."""

import subprocess

from openadmindesk.core import x11_detector
from openadmindesk.core.x11_detector import X11Detector


def test_x11_detector_reads_display_environment(monkeypatch) -> None:
    monkeypatch.setenv("DISPLAY", ":99")

    assert X11Detector.get_x11_display() == ":99"


def test_x11_detector_reports_xwayland_process(monkeypatch) -> None:
    monkeypatch.setattr(x11_detector, "is_linux", lambda: True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="123\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert X11Detector.is_xwayland_available() is True


def test_x11_detector_returns_xauth_output(monkeypatch) -> None:
    monkeypatch.setattr(x11_detector, "is_linux", lambda: True)
    monkeypatch.setattr(x11_detector, "is_macos", lambda: False)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="cookie\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert X11Detector.get_x11_auth() == "cookie"
