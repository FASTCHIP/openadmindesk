"""VNC session tab widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
)
from PySide6.QtCore import Qt, Signal

from openadmindesk.core.vnc_backend import VncBackend
from openadmindesk.core.profile import Profile
from openadmindesk.core.l10n import _

_STATUS_COLORS = {
    "disconnected": "color: #e05555; font-weight: bold;",
    "connecting": "color: #dcaa3a; font-weight: bold;",
    "connected": "color: #4ec94e; font-weight: bold;",
}


class VncSessionTab(QWidget):
    tab_closed = Signal()

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self.profile = profile
        self.backend = VncBackend(profile)
        self._connected = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel(f"🖵  {self.profile.name}")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #cccccc;")
        layout.addWidget(header)

        sub = QLabel(f"{self.profile.host}:{self.profile.port or 5900}")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 13px; color: #969696;")
        layout.addWidget(sub)
        layout.addSpacing(20)

        self.status_label = QLabel(_("● Disconnected"))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(_STATUS_COLORS["disconnected"])
        layout.addWidget(self.status_label)
        layout.addSpacing(16)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.connect_button = QPushButton(_("Connect"))
        self.connect_button.setMinimumWidth(140)
        self.connect_button.clicked.connect(self._toggle_connection)
        btn_layout.addWidget(self.connect_button)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addSpacing(12)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(80)
        layout.addWidget(self.info_text)

        if not VncBackend.is_available():
            self.status_label.setText("⚠  VNC viewer not installed")
            self.status_label.setStyleSheet(_STATUS_COLORS["connecting"])
            self.connect_button.setEnabled(False)
            self.info_text.setPlainText(
                _("No VNC viewer found.\nInstall: vncviewer, vinagre, or remmina.")
            )

        layout.addStretch()

    def _toggle_connection(self) -> None:
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        self.connect_button.setEnabled(False)
        self.status_label.setText(_("● Connecting..."))
        self.status_label.setStyleSheet(_STATUS_COLORS["connecting"])

        # Show VNC options being used
        options = []
        if getattr(self.profile, "vnc_scaling", False):
            options.append("scaling=on")
        if getattr(self.profile, "vnc_view_only", False):
            options.append("view-only")
        depth = getattr(self.profile, "vnc_color_depth", 24)
        if depth != 24:
            options.append(f"depth={depth}")
        viewer = self.backend._viewer or "vncviewer"
        diag = f"Viewer: {viewer}\nOptions: {', '.join(options) if options else 'default'}"
        self.info_text.setPlainText(diag)

        success = self.backend.connect()
        if success:
            self._connected = True
            self.status_label.setText(_("● Connected (VNC window)"))
            self.status_label.setStyleSheet(_STATUS_COLORS["connected"])
            self.connect_button.setText(_("Disconnect"))
            self.connect_button.setEnabled(True)
            self.info_text.append("\nVNC session active.")
        else:
            self.status_label.setText(_("● Connection Failed"))
            self.status_label.setStyleSheet(_STATUS_COLORS["disconnected"])
            self.connect_button.setEnabled(True)
            error = self.backend.last_error()
            if error:
                self.info_text.append(f"\nError: {error[:300]}")

    def _disconnect(self) -> None:
        self.backend.disconnect()
        self._connected = False
        self.status_label.setText(_("● Disconnected"))
        self.status_label.setStyleSheet(_STATUS_COLORS["disconnected"])
        self.connect_button.setText(_("Connect"))
        self.connect_button.setEnabled(True)
        self.info_text.setPlainText("")

    def closeEvent(self, event) -> None:
        if self._connected:
            self._disconnect()
        self.tab_closed.emit()
        event.accept()
