"""Tests for activity rail widget."""

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from openadmindesk.ui.activity_rail import ActivityRail


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """Create a Qt application for testing."""
    app = QApplication.instance() or QApplication([])
    yield app


def test_activity_rail_initialization():
    """Test that activity rail initializes correctly."""
    rail = ActivityRail()
    assert rail is not None
    assert rail.minimumWidth() == 280
    assert rail.maximumWidth() == 350
    assert list(rail.mode_buttons) == ["sessions", "tunnels", "tools"]
    assert list(rail.mode_widgets) == ["sessions", "tunnels", "tools"]


def test_activity_rail_modes():
    """Test that all modes are available."""
    rail = ActivityRail(include_planned_modes=True)
    expected_modes = ["sessions", "sftp", "tunnels", "tools", "macros", "vault"]
    
    for mode in expected_modes:
        assert mode in rail.mode_buttons
        assert mode in rail.mode_widgets


def test_activity_rail_mode_switching():
    """Test mode switching functionality."""
    rail = ActivityRail(include_planned_modes=True)
    
    # Initially sessions mode should be active
    assert rail.mode_buttons["sessions"].isChecked()
    
    # Switch to SFTP mode
    rail._set_mode("sftp")
    assert rail.mode_buttons["sftp"].isChecked()
    assert not rail.mode_buttons["sessions"].isChecked()
    
    # Switch to tunnels mode
    rail._set_mode("tunnels")
    assert rail.mode_buttons["tunnels"].isChecked()
    assert not rail.mode_buttons["sftp"].isChecked()


def test_activity_rail_set_widgets():
    """Test setting custom widgets for modes."""
    rail = ActivityRail(include_planned_modes=True)
    
    # Create test widgets
    test_widget1 = QWidget()
    test_widget2 = QWidget()
    test_widget3 = QWidget()
    
    # Set custom widgets
    rail.set_sessions_widget(test_widget1)
    rail.set_sftp_widget(test_widget2)
    rail.set_tunnels_widget(test_widget3)
    
    # Verify widgets are set
    assert rail.mode_widgets["sessions"] == test_widget1
    assert rail.mode_widgets["sftp"] == test_widget2
    assert rail.mode_widgets["tunnels"] == test_widget3


def test_activity_rail_signal_emission():
    """Test that mode_changed signal is emitted."""
    rail = ActivityRail(include_planned_modes=True)
    emitted_modes = []
    
    def on_mode_changed(mode):
        emitted_modes.append(mode)
    
    rail.mode_changed.connect(on_mode_changed)
    
    # Switch modes
    rail._set_mode("sftp")
    rail._set_mode("tunnels")
    rail._set_mode("vault")
    
    # Verify signals were emitted
    assert len(emitted_modes) == 3
    assert emitted_modes == ["sftp", "tunnels", "vault"]


def test_activity_rail_size_constraints():
    """Test that size constraints are properly set."""
    rail = ActivityRail()
    
    # Check minimum and maximum width
    assert rail.minimumWidth() == 280
    assert rail.maximumWidth() == 350
    
    # The rail should not be resizable beyond these limits
    rail.setMinimumWidth(200)  # This should not change anything
    rail.setMaximumWidth(400)  # This should not change anything
    assert rail.minimumWidth() == 280
    assert rail.maximumWidth() == 350