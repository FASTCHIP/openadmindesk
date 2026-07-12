"""Tests for the main application entrypoint."""

from unittest.mock import MagicMock, patch

from openadmindesk.app import main


def test_main_creates_window_and_returns_event_loop_code() -> None:
    """main() should wire Qt objects without entering a real event loop in tests."""
    app = MagicMock()
    app.exec.return_value = 0
    window = MagicMock()

    with (
        patch("sys.argv", ["openadmindesk"]),
        patch("openadmindesk.app.QApplication", return_value=app) as qapp,
        patch("openadmindesk.app.apply_theme") as apply_theme,
        patch("openadmindesk.app.create_main_window", return_value=window),
        patch("openadmindesk.app.is_portable", return_value=False),
    ):
        assert main() == 0

    qapp.assert_called_once_with(["openadmindesk"])
    apply_theme.assert_called_once_with(app)
    window.show.assert_called_once_with()
    app.exec.assert_called_once_with()


def test_main_enables_portable_mode_before_window_creation() -> None:
    """--portable should be consumed and portable title applied after window creation."""
    app = MagicMock()
    app.exec.return_value = 0
    window = MagicMock()

    with (
        patch("sys.argv", ["openadmindesk", "--portable"]),
        patch("openadmindesk.app.QApplication", return_value=app) as qapp,
        patch("openadmindesk.app.apply_theme"),
        patch("openadmindesk.app.create_main_window", return_value=window),
        patch("openadmindesk.app.enable_portable_mode") as enable_portable_mode,
        patch("openadmindesk.app.is_portable", return_value=True),
    ):
        assert main() == 0

    enable_portable_mode.assert_called_once_with()
    qapp.assert_called_once_with(["openadmindesk"])
    window.setWindowTitle.assert_called_once_with("OpenAdminDesk [PORTABLE]")
    window.show.assert_called_once_with()

def test_main_version_prints_without_qt(capsys) -> None:
    """--version should return before creating QApplication."""
    with (
        patch("sys.argv", ["openadmindesk", "--version"]),
        patch("openadmindesk.app.QApplication") as qapp,
        patch("openadmindesk.app._version", return_value="1.2.3"),
    ):
        assert main() == 0

    assert "OpenAdminDesk 1.2.3" in capsys.readouterr().out
    qapp.assert_not_called()
