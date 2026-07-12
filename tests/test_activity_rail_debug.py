"""Regression tests for activity rail widget installation."""

from PySide6.QtWidgets import QWidget

from openadmindesk.ui.activity_rail import ActivityRail


def test_activity_rail_replaces_mode_widget_without_losing_order() -> None:
    rail = ActivityRail()
    original_index = rail.content_stack.indexOf(rail.mode_widgets["sessions"])
    replacement = QWidget()

    rail.set_sessions_widget(replacement)

    assert rail.mode_widgets["sessions"] is replacement
    assert rail.content_stack.indexOf(replacement) == original_index
    assert rail.content_stack.currentWidget() is replacement


def test_activity_rail_rejects_unknown_mode_without_changing_current_mode() -> None:
    rail = ActivityRail()
    before = rail.content_stack.currentWidget()

    rail._set_mode("unknown")

    assert rail.content_stack.currentWidget() is before
    assert rail.mode_buttons["sessions"].isChecked()
