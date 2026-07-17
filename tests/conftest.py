"""Shared test fixtures and configuration for OpenAdminDesk tests."""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest

# Add src to path so tests can import from openadmindesk
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files, cleaned up after test."""
    tmp = tempfile.mkdtemp(prefix="oad_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_profile_dict() -> dict:
    """Return a minimal valid profile as a dictionary."""
    return {
        "name": "test-server",
        "host": "192.168.1.1",
        "port": 22,
        "username": "admin",
        "password": None,
        "private_key_path": None,
        "use_ssh_agent": False,
        "compression": False,
        "keep_alive": True,
        "ssh_config": None,
        "proxy_command": None,
    }


@pytest.fixture
def sample_account_dict() -> dict:
    """Return a minimal valid account as a dictionary."""
    return {
        "name": "test-account",
        "username": "root",
        "password": "fake-password-123",
        "host": "example.com",
        "port": 22,
        "service_type": "ssh",
    }


@pytest.fixture
def vault_path(temp_dir: Path) -> Path:
    """Return a path for a temporary vault file."""
    return temp_dir / "test_vault.json"


@pytest.fixture
def snippet_path(temp_dir: Path) -> Path:
    """Return a path for a temporary snippet file."""
    return temp_dir / "test_snippets.json"

@pytest.fixture(scope="session")
def qapp():
    """Create one QApplication for Qt widget tests in headless mode."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(["openadmindesk-tests"])
    return app


QT_TEST_FILES = {
    "test_app.py",
    "test_attached_sftp.py",
    "test_connection_event_area.py",
    "test_connection_tree.py",
    "test_gui_launcher.py",
    "test_local_shell_tab.py",
    "test_main_window.py",
    "test_main_window_workspace.py",
    "test_profile_editor.py",
    "test_quick_connect_toolbar.py",
    "test_session_wizard.py",
    "test_sftp_file_browser.py",
    "test_snippet_inserter.py",
    "test_ssh_terminal_tab.py",
    "test_tabbed_workspace.py",
    "test_terminal_widget.py",
    "test_telnet_session_tab.py",
    "test_tunnel_manager.py",
    "test_workspace_container.py",
    "test_workspace_routing.py",
}


def pytest_collection_modifyitems(items):
    qt_marker = pytest.mark.qt
    for item in items:
        if Path(str(item.fspath)).name in QT_TEST_FILES:
            item.add_marker(qt_marker)


@pytest.fixture(autouse=True)
def _ensure_qapp_for_qt_tests(request):
    """Create QApplication only for tests marked as Qt/UI tests."""
    if request.node.get_closest_marker("qt") is None:
        return None
    return request.getfixturevalue("qapp")

