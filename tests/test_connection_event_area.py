"""Tests for connection event area."""

from openadmindesk.ui.connection_event_area import ConnectionEventArea


def test_connection_event_area_updates_status_activity_and_session_count() -> None:
    event_area = ConnectionEventArea()

    event_area.set_connection_status("Connected")
    event_area.set_activity("Opening session")
    event_area.update_session_count(2, 3)

    assert event_area.connection_status.text() == "Connected"
    assert event_area.activity_indicator.text() == "Opening session"
    assert event_area.session_count.text() == "🔌 2/3"

    event_area.update_session_count(0, 0)
    assert event_area.session_count.text() == ""
