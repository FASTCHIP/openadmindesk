"""Tests for the main application entrypoint."""

from unittest.mock import MagicMock, patch

from openadmindesk.app import main


def test_main_creates_window_and_returns_event_loop_code() -> None:
    """main() should wire Qt objects without entering a real event loop in tests."""
    app = MagicMock()
    app.exec.return_value = 0
    window = MagicMock()
    qapp_mock = MagicMock(return_value=app)
    is_portable_mock = MagicMock(return_value=False)

    with (
        patch("sys.argv", ["openadmindesk"]),
    ):
        with patch("openadmindesk.app._load_gui_dependencies", return_value=(
            qapp_mock, lambda: window, MagicMock(), MagicMock(), is_portable_mock
        )):
            assert main() == 0

    qapp_mock.assert_called_once_with(["openadmindesk"])
    is_portable_mock.assert_called_once_with()
    window.show.assert_called_once_with()
    app.exec.assert_called_once_with()


def test_main_enables_portable_mode_before_window_creation() -> None:
    """--portable should be consumed and portable title applied after window creation."""
    app = MagicMock()
    app.exec.return_value = 0
    window = MagicMock()
    qapp_mock = MagicMock(return_value=app)
    is_portable_mock = MagicMock(return_value=True)
    enable_portable_mock = MagicMock()

    with (
        patch("sys.argv", ["openadmindesk", "--portable"]),
    ):
        with patch("openadmindesk.app._load_gui_dependencies", return_value=(
            qapp_mock, lambda: window, MagicMock(), enable_portable_mock, is_portable_mock
        )):
            assert main() == 0

    enable_portable_mock.assert_called_once_with()
    qapp_mock.assert_called_once_with(["openadmindesk"])
    window.setWindowTitle.assert_called_once_with("OpenAdminDesk [PORTABLE]")
    window.show.assert_called_once_with()


def test_main_version_prints_without_qt(capsys) -> None:
    """--version should return before creating QApplication."""
    with (
        patch("sys.argv", ["openadmindesk", "--version"]),
        patch("openadmindesk.app._version", return_value="1.2.3"),
        patch("openadmindesk.app._load_gui_dependencies") as mock_load_deps,
    ):
        assert main() == 0

    assert "OpenAdminDesk 1.2.3" in capsys.readouterr().out
    mock_load_deps.assert_not_called()
