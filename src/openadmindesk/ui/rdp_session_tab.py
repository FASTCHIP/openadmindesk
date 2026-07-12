"""RDP session tab widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PySide6.QtCore import Qt, Signal

from openadmindesk.core.rdp_backend import RdpBackend
from openadmindesk.core.profile import Profile
from openadmindesk.core.l10n import _


class RdpSessionTab(QWidget):
    """Tab for an RDP remote desktop session.

    Since xfreerdp opens its own window, this tab acts as a control panel
    showing connection status and offering connect/disconnect actions.
    """

    tab_closed = Signal()

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self.profile = profile
        self.backend = RdpBackend(profile)
        self._connected = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel(f"🖥  {self.profile.name}")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #cccccc;"
        )
        layout.addWidget(header)

        sub = QLabel(
            f"{self.profile.username}@{self.profile.host}:{self.profile.port}"
        )
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 13px; color: #969696;")
        layout.addWidget(sub)

        layout.addSpacing(20)

        # Status label
        self.status_label = QLabel(_("● Disconnected"))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "font-size: 15px; color: #e05555; font-weight: bold;"
        )
        layout.addWidget(self.status_label)

        layout.addSpacing(16)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.connect_button = QPushButton(_("Connect"))
        self.connect_button.setMinimumWidth(140)
        self.connect_button.clicked.connect(self._toggle_connection)
        btn_layout.addWidget(self.connect_button)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addSpacing(12)

        # Info text
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(80)
        self.info_text.setPlaceholderText(_("Session information..."))
        layout.addWidget(self.info_text)

        # Check availability
        if not RdpBackend.is_available():
            self.status_label.setText(_("⚠  xfreerdp not installed"))
            self.status_label.setStyleSheet(
                "font-size: 15px; color: #dcaa3a; font-weight: bold;"
            )
            self.connect_button.setEnabled(False)
            self.info_text.setPlainText(
                "xfreerdp is not installed on this system.\n\n"
                "Install it:\n"
                "  Ubuntu:  sudo apt install freerdp2-x11\n"
                "  Fedora:  sudo dnf install freerdp"
            )

        layout.addStretch()

    def _toggle_connection(self) -> None:
        """Connect or disconnect."""
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """Start RDP session."""
        self.connect_button.setEnabled(False)
        self.status_label.setText(_("● Launching RDP..."))
        self.status_label.setStyleSheet(
            "font-size: 15px; color: #dcaa3a; font-weight: bold;"
        )

        success = self.backend.connect()
        if success:
            self._connected = True
            self.status_label.setText(_("● Connected (RDP window opened)"))
            self.status_label.setStyleSheet(
                "font-size: 15px; color: #4ec94e; font-weight: bold;"
            )
            self.connect_button.setText(_("Disconnect"))
            self.connect_button.setEnabled(True)
            self.info_text.setPlainText(
                "RDP session is active. The remote desktop opened in a "
                "separate window.\n\n"
                "Close the RDP window to end the session, or click Disconnect."
            )
        else:
            self.status_label.setText(_("● Connection Failed"))
            self.status_label.setStyleSheet(
                "font-size: 15px; color: #e05555; font-weight: bold;"
            )
            self.connect_button.setEnabled(True)

    def _disconnect(self) -> None:
        """End RDP session."""
        self.backend.disconnect()
        self._connected = False
        self.status_label.setText(_("● Disconnected"))
        self.status_label.setStyleSheet(
            "font-size: 15px; color: #e05555; font-weight: bold;"
        )
        self.connect_button.setText(_("Connect"))
        self.connect_button.setEnabled(True)
        self.info_text.setPlainText("")

    def closeEvent(self, event) -> None:
        """Clean up on tab close."""
        if self._connected:
            self._disconnect()
        self.tab_closed.emit()
        event.accept()
