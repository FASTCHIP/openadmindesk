"""Connection event area — enhanced status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel

from openadmindesk.core.l10n import _


class ConnectionEventArea(QStatusBar):
    """Status bar with session counters and connection state."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_event_area()

    def _setup_event_area(self) -> None:
        self.connection_status = QLabel(_("● Disconnected"))
        self.connection_status.setStyleSheet("color: #e05555; padding: 0 8px;")
        self.addPermanentWidget(self.connection_status, 0)

        self.session_count = QLabel("")
        self.session_count.setStyleSheet("color: #969696; padding: 0 8px;")
        self.addPermanentWidget(self.session_count, 0)

        self.activity_indicator = QLabel("")
        self.addPermanentWidget(self.activity_indicator, 1)

    def set_connection_status(self, status: str) -> None:
        self.connection_status.setText(status)

    def update_session_count(self, connected: int, total: int) -> None:
        """Update the session counter label."""
        if connected > 0:
            color = "#4ec94e"
        elif total > 0:
            color = "#dcaa3a"
        else:
            self.session_count.setText("")
            return
        self.session_count.setStyleSheet(f"color: {color}; padding: 0 8px;")
        self.session_count.setText(f"🔌 {connected}/{total}")

    def set_activity(self, activity: str) -> None:
        self.activity_indicator.setText(activity)
