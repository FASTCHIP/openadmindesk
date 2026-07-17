"""Telnet session tab widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QToolBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer

from openadmindesk.core.telnet_backend import TelnetBackend
from openadmindesk.core.profile import Profile
from openadmindesk.ui.terminal_widget import TerminalWidget
from openadmindesk.ui.terminal_theme import get_theme
from openadmindesk.ui.terminal_settings import TerminalSettingsDialog
from openadmindesk.core.l10n import _

_STATUS_DISCONNECTED = "color: #e05555; font-weight: bold;"
_STATUS_CONNECTING = "color: #dcaa3a; font-weight: bold;"
_STATUS_CONNECTED = "color: #4ec94e; font-weight: bold;"


class TelnetSessionTab(QWidget):
    """Telnet terminal tab using telnetlib3 + terminal widget."""

    connection_status_changed = Signal(bool)
    tab_closed = Signal()

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self.profile = profile
        self.backend = TelnetBackend(profile)
        self._connected = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QToolBar()
        info_text = f"{self.profile.username}@{self.profile.host}:{self.profile.port or 23}"
        self.info_label = QLabel(info_text)
        toolbar.addWidget(self.info_label)

        toolbar.addSeparator()
        self.status_label = QLabel(_("● Disconnected"))
        self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
        toolbar.addWidget(self.status_label)
        toolbar.addSeparator()

        self.connect_button = QPushButton(_("Connect"))
        self.connect_button.clicked.connect(self._toggle_connection)
        toolbar.addWidget(self.connect_button)

        self.reconnect_button = QPushButton(_("Reconnect"))
        self.reconnect_button.clicked.connect(self._on_reconnect)
        self.reconnect_button.setEnabled(False)
        toolbar.addWidget(self.reconnect_button)

        toolbar.addSeparator()
        settings_btn = QPushButton(_("⚙"))
        settings_btn.setToolTip(_("Terminal Settings (theme, font, opacity)"))
        settings_btn.clicked.connect(self._show_terminal_settings)
        toolbar.addWidget(settings_btn)

        layout.addWidget(toolbar)

        self.terminal = TerminalWidget(columns=120, rows=40)
        self.terminal.key_pressed.connect(self._on_key_pressed)
        self.terminal.setContextMenuPolicy(Qt.CustomContextMenu)
        self.terminal.customContextMenuRequested.connect(self._terminal_context_menu)
        theme = get_theme(self.profile.terminal_theme)
        self.terminal.set_theme(theme)
        layout.addWidget(self.terminal)

    def _toggle_connection(self) -> None:
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _confirm_cleartext_connection(self) -> bool:
        """Show warning dialog for cleartext connection and return user's choice."""
        title = _("Telnet Connection Warning")
        body = _("This connection uses the Telnet protocol, which transmits credentials and session data in plaintext over the network. Network observers can read your username, password, and all session data. Only use this connection type for trusted legacy systems.")
        try:
            button = QMessageBox.warning(
                self,
                title,
                body,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return button == QMessageBox.Yes
        except Exception:
            # Fail closed on dialog exception
            return False

    def _start_connection(self) -> None:
        """Start connection process after warning confirmation."""
        self.connect_button.setEnabled(False)
        self.status_label.setText(_("● Connecting..."))
        self.status_label.setStyleSheet(_STATUS_CONNECTING)

        def on_output(data: str) -> None:
            self.terminal.feed(data if isinstance(data, str) else data.decode("utf-8", errors="replace"))

        def do_connect() -> None:
            success = self.backend.connect(on_output=on_output)
            if success:
                self._connected = True
                self.status_label.setText(_("● Connected"))
                self.status_label.setStyleSheet(_STATUS_CONNECTED)
                self.connect_button.setText(_("Disconnect"))
                self.reconnect_button.setEnabled(True)
                self.connection_status_changed.emit(True)
            else:
                self.status_label.setText(_("● Connection Failed"))
                self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
                self.connection_status_changed.emit(False)
            self.connect_button.setEnabled(True)

        QTimer.singleShot(50, do_connect)

    def _connect(self) -> None:
        """Connect to Telnet server with warning dialog."""
        # Show warning dialog before connecting
        if not self._confirm_cleartext_connection():
            # User cancelled, do not proceed with connection
            return

        # User confirmed, proceed with connection
        self._start_connection()

    def _on_reconnect(self) -> None:
        """Reconnect to Telnet server with warning dialog."""
        # Show warning dialog before reconnecting
        if not self._confirm_cleartext_connection():
            # User cancelled, preserve connection state
            return

        # User confirmed, disconnect and reconnect
        self._disconnect()
        self._start_connection()

    def _on_key_pressed(self, text: str) -> None:
        self.backend.send(text)

    def _disconnect(self) -> None:
        self.backend.disconnect()
        self._connected = False
        self.status_label.setText(_("● Disconnected"))
        self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
        self.connect_button.setText(_("Connect"))
        self.reconnect_button.setEnabled(False)
        self.connection_status_changed.emit(False)

    def _terminal_context_menu(self, position) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        menu.addAction(_("⚙ Terminal Settings..."), self._show_terminal_settings)
        menu.addSeparator()
        menu.addAction(_("Clear Terminal"), self.terminal.clear)
        menu.exec(self.terminal.mapToGlobal(position))

    def _show_terminal_settings(self) -> None:
        dlg = TerminalSettingsDialog(self.terminal.theme, self)
        if dlg.exec() == TerminalSettingsDialog.Accepted:
            self.terminal.set_theme(dlg.result_theme())
            self.profile.terminal_theme = dlg.result_theme().name

    def closeEvent(self, event) -> None:
        if self._connected:
            self._disconnect()
        self.tab_closed.emit()
        event.accept()
