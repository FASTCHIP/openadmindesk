"""RDP session tab widget — embedded FreeRDP display."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

from openadmindesk.core.rdp_client import RdpClient
from openadmindesk.core.profile import Profile
from openadmindesk.ui.rdp_display import RdpDisplay
from openadmindesk.core.l10n import _


class RdpSessionTab(QWidget):
    """Tab for an embedded RDP remote desktop session.

    Uses RdpClient (FreeRDP via ctypes) for connection and
    RdpDisplay for frame rendering and input capture.
    """

    tab_closed = Signal()
    status_message = Signal(str)

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self.profile = profile
        self._client = RdpClient(profile)
        self._connected = False
        self._setup_ui()
        self._wire_client()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)

        # ── header ────────────────────────────────────────────────────
        header = QLabel(f"🖥  {self.profile.name}")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #cccccc; padding: 4px;"
        )
        layout.addWidget(header)

        sub = QLabel(
            f"{self.profile.username}@{self.profile.host}:{self.profile.port}"
        )
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #969696;")
        layout.addWidget(sub)

        # ── toolbar ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        self._status_label = QLabel(_("● Disconnected"))
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #e05555; font-weight: bold;"
        )
        toolbar.addWidget(self._status_label)

        toolbar.addStretch()

        self._connect_button = QPushButton(_("Connect"))
        self._connect_button.setMinimumWidth(120)
        self._connect_button.clicked.connect(self._toggle_connection)
        toolbar.addWidget(self._connect_button)

        self._cad_button = QPushButton(_("Ctrl+Alt+Del"))
        self._cad_button.setMinimumWidth(120)
        self._cad_button.clicked.connect(self._send_cad)
        self._cad_button.setEnabled(False)
        toolbar.addWidget(self._cad_button)

        self._fullscreen_button = QPushButton(_("Fullscreen"))
        self._fullscreen_button.setMinimumWidth(120)
        self._fullscreen_button.clicked.connect(self._toggle_fullscreen)
        toolbar.addWidget(self._fullscreen_button)

        layout.addLayout(toolbar)

        # ── RDP display ───────────────────────────────────────────────
        self._display = RdpDisplay(self._client, self)
        layout.addWidget(self._display, 1)  # stretch factor 1

    def _wire_client(self) -> None:
        """Connect RdpClient signals to UI updates."""
        self._client.connected.connect(self._on_connected)
        self._client.disconnected.connect(self._on_disconnected)
        self._client.error_occurred.connect(self._on_error)
        self._client.certificate_prompt.connect(self._on_certificate_prompt)
        self._client.clipboard_text_received.connect(self._on_clipboard_received)

    # ── connection control ────────────────────────────────────────────

    def _toggle_connection(self) -> None:
        """Connect or disconnect."""
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """Start RDP session."""
        if self.profile.username and not self.profile.password:
            from PySide6.QtWidgets import QInputDialog, QLineEdit
            pwd, ok = QInputDialog.getText(
                self, _("RDP Password"),
                _("Enter password for {}:").format(f"{self.profile.username}@{self.profile.host}"),
                QLineEdit.Password
            )
            if ok and pwd:
                self.profile.password = pwd
            else:
                self._connected = False
                self._connect_button.setText(_("Connect"))
                self._connect_button.setEnabled(True)
                self._status_label.setText(_("● Password required"))
                self.status_message.emit(_("RDP connection failed: Password required"))
                return

        self._connect_button.setEnabled(False)
        self._status_label.setText(_("● Connecting..."))
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #dcaa3a; font-weight: bold;"
        )
        self._client.connect_to_host()

    def _disconnect(self) -> None:
        """End RDP session."""
        self._client.disconnect()

    def _send_cad(self) -> None:
        """Send Ctrl+Alt+Del to the remote session."""
        if self._connected:
            self._client.send_ctrl_alt_del()

    # ── RdpClient signal handlers ─────────────────────────────────────

    def _on_connected(self) -> None:
        self._connected = True
        self._status_label.setText(_("● Connected"))
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #4ec94e; font-weight: bold;"
        )
        self._connect_button.setText(_("Disconnect"))
        self._connect_button.setEnabled(True)
        self._cad_button.setEnabled(True)

    def _on_disconnected(self) -> None:
        self._connected = False
        self._status_label.setText(_("● Disconnected"))
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #e05555; font-weight: bold;"
        )
        self._connect_button.setText(_("Connect"))
        self._connect_button.setEnabled(True)
        self._cad_button.setEnabled(False)

    def _on_error(self, message: str) -> None:
        detail = (message or '').strip() or _("Unknown RDP error")
        label_text = (detail[:90] + '...') if len(detail) > 93 else detail

        self._connected = False
        self._connect_button.setText(_("Connect"))
        self._connect_button.setEnabled(True)
        self._cad_button.setEnabled(False)

        self._status_label.setText(f"● Error: {label_text}")
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #e05555; font-weight: bold;"
        )
        self._status_label.setToolTip(detail)
        self.status_message.emit(f"RDP connection failed: {detail}")
 
    def _on_certificate_prompt(self, host, fingerprint, subject, issuer):
        from PySide6.QtWidgets import QMessageBox
        msg = (
            f"The RDP server certificate for {host} is not trusted yet.\n\n"
            f"Subject: {subject}\n"
            f"Issuer: {issuer}\n"
            f"Fingerprint (SHA-256): {fingerprint}\n\n"
            "Only trust it if this fingerprint is expected.\n"
            "Trusting will store the fingerprint for future connections."
        )
        reply = QMessageBox.question(
            self, "Trust RDP Server Certificate", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        self._client.set_certificate_decision(reply == QMessageBox.Yes)
 
    # ── lifecycle ─────────────────────────────────────────────────────


    def closeEvent(self, event) -> None:
        """Clean up on tab close."""
        if self._connected:
            self._disconnect()
        self.tab_closed.emit()
        event.accept()

    def _toggle_fullscreen(self) -> None:
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
            self._fullscreen_button.setText(_("Fullscreen"))
        else:
            win.showFullScreen()
            self._fullscreen_button.setText(_("Window"))

    def _on_clipboard_received(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
