"""SSH terminal tab widget — self-contained (paramiko + pyte)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolBar,
    QMenu,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot, QTimer
try:
    from PySide6.QtGui import QAction  # PySide6 >= 6.11
except ImportError:
    from PySide6.QtWidgets import QAction
from typing import Optional

from openadmindesk.core.ssh_terminal_backend import SSHTerminalBackend
from openadmindesk.core.profile import Profile
from openadmindesk.core.snippet_store import SnippetStore
from openadmindesk.ui.terminal_widget import TerminalWidget
from openadmindesk.ui.terminal_theme import get_theme
from openadmindesk.ui.terminal_settings import TerminalSettingsDialog
from openadmindesk.ui.snippet_manager import SnippetInsertButton
from openadmindesk.ui.sftp_file_browser import SftpFileBrowser
from openadmindesk.core.l10n import _

class _SshConnectWorker(QObject):
    """Runs a blocking SSH connection attempt outside the UI thread."""

    output = Signal(bytes)
    finished = Signal(bool, str)

    def __init__(self, backend: SSHTerminalBackend) -> None:
        super().__init__()
        self._backend = backend

    @Slot()
    def run(self) -> None:
        try:
            success = self._backend.connect(on_output=self.output.emit)
            error = "" if success else self._backend.last_error()
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            success = False
            error = str(exc)
        self.finished.emit(success, error or "")

    @Slot()
    def cancel(self) -> None:
        self._backend.disconnect()


# Status colors (matching theme.py)
_STATUS_DISCONNECTED = "color: #e05555; font-weight: bold;"
_STATUS_CONNECTING = "color: #dcaa3a; font-weight: bold;"
_STATUS_CONNECTED = "color: #4ec94e; font-weight: bold;"


class SshTerminalTab(QWidget):
    """Self-contained SSH terminal tab using paramiko + pyte terminal emulator."""

    connection_status_changed = Signal(bool)
    sftp_requested = Signal(Profile)
    tab_closed = Signal()
    attached_sftp_opened = Signal()
    attached_sftp_closed = Signal()
    broadcast_opt_in_changed = Signal(bool)

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self.profile = profile
        self.backend = SSHTerminalBackend(profile)
        self.snippet_store = SnippetStore()
        self._connected = False
        self._broadcast_opted_in = False
        self._macro_recording = False
        self._macro_keys: list[str] = []
        self._last_macro: list[str] = []
        self._monitor_timer: Optional[QTimer] = None
        self._connect_thread: Optional[QThread] = None
        self._connect_worker: Optional[_SshConnectWorker] = None
        self._connect_cancelled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main content area with splitter for attached SFTP
        self._main_content = QWidget()
        self._main_layout = QHBoxLayout(self._main_content)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(4)
        
        # Terminal area (always present)
        self.terminal = TerminalWidget()
        self.terminal.set_theme(get_theme("default"))
        self.terminal.set_bg_opacity(242)
        self.terminal.key_pressed.connect(self._on_key_pressed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocusProxy(self.terminal)
        self._main_layout.addWidget(self.terminal)
        
        # Attached SFTP panel (initially empty)
        self._attached_sftp_panel = QWidget()
        self._attached_sftp_panel.setVisible(False)
        self._attached_sftp_layout = QVBoxLayout(self._attached_sftp_panel)
        self._attached_sftp_layout.setContentsMargins(0, 0, 0, 0)
        self._attached_sftp_browser: Optional[SftpFileBrowser] = None
        
        self._main_layout.addWidget(self._attached_sftp_panel)
        
        main_layout.addWidget(self._main_content)
        
        # Toolbar
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        info_text = f"{self.profile.username}@{self.profile.host}:{self.profile.port}"
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

        self.trust_host_button = QPushButton(_("Trust Host Key"))
        self.trust_host_button.clicked.connect(self._trust_pending_host_key)
        self.trust_host_button.setEnabled(False)
        toolbar.addWidget(self.trust_host_button)

        toolbar.addSeparator()

        self.sftp_button = QPushButton(_("📁 SFTP"))
        self.sftp_button.setCheckable(True)
        self.sftp_button.clicked.connect(self._toggle_sftp_browser)
        self.sftp_button.setEnabled(False)
        toolbar.addWidget(self.sftp_button)
        
        # Attached SFTP controls
        self.sftp_attach_btn = QPushButton(_("📁 Attach SFTP"))
        self.sftp_attach_btn.setEnabled(False)
        self.sftp_attach_btn.clicked.connect(self.open_attached_sftp)
        toolbar.addWidget(self.sftp_attach_btn)
        
        self.sftp_detach_btn = QPushButton(_("📁 Detach SFTP"))
        self.sftp_detach_btn.setEnabled(False)
        self.sftp_detach_btn.clicked.connect(self.detach_attached_sftp)
        toolbar.addWidget(self.sftp_detach_btn)
        
        self.sftp_close_btn = QPushButton(_("✕ Close SFTP"))
        self.sftp_close_btn.setEnabled(False)
        self.sftp_close_btn.clicked.connect(self.close_attached_sftp)
        toolbar.addWidget(self.sftp_close_btn)

        self.snippet_button = SnippetInsertButton(self.snippet_store)
        self.snippet_button.snippet_insert_requested.connect(
            self._on_snippet_insert
        )
        self.snippet_button.setEnabled(False)
        toolbar.addWidget(self.snippet_button)

        toolbar.addSeparator()

        # Macro recording buttons
        self.macro_record_btn = QPushButton("⏺")
        self.macro_record_btn.setToolTip("Record Macro")
        self.macro_record_btn.setCheckable(True)
        self.macro_record_btn.clicked.connect(self._toggle_macro_recording)
        self.macro_record_btn.setEnabled(False)
        toolbar.addWidget(self.macro_record_btn)

        self.macro_play_btn = QPushButton("▶")
        self.macro_play_btn.setToolTip("Play last macro")
        self.macro_play_btn.clicked.connect(self._play_macro)
        self.macro_play_btn.setEnabled(False)
        toolbar.addWidget(self.macro_play_btn)

        toolbar.addSeparator()

        # Remote Monitor
        self.monitor_btn = QPushButton("📊")
        self.monitor_btn.setToolTip("Remote Monitor (CPU, RAM, Disk)")
        self.monitor_btn.setCheckable(True)
        self.monitor_btn.clicked.connect(self._toggle_monitor)
        self.monitor_btn.setEnabled(False)
        toolbar.addWidget(self.monitor_btn)

        toolbar.addSeparator()

        settings_btn = QPushButton(_("⚙"))
        settings_btn.setToolTip(_("Terminal Settings (theme, font, opacity)"))
        settings_btn.clicked.connect(self._show_terminal_settings)
        toolbar.addWidget(settings_btn)

        main_layout.addWidget(toolbar)

        # Broadcast opt-in banner (hidden by default)
        self._broadcast_banner = QLabel()
        self._broadcast_banner.setVisible(False)
        self._broadcast_banner.setStyleSheet(
            "QLabel { background-color: #094771; color: #4ec94e; "
            "font-weight: bold; padding: 4px 8px; font-size: 12px; "
            "border: 1px solid #007acc; }"
        )
        main_layout.addWidget(self._broadcast_banner)

        # Apply saved theme from profile
        theme = get_theme(self.profile.terminal_theme)
        self.terminal.set_theme(theme)
        self.sftp_browser: Optional[object] = None
        self._sftp_visible = False

    # ── broadcast opt-in ─────────────────────────────────────────────────────

    @property
    def broadcast_opted_in(self) -> bool:
        """Whether this tab has opted into MultiExec broadcast."""
        return self._broadcast_opted_in

    @broadcast_opted_in.setter
    def broadcast_opted_in(self, value: bool) -> None:
        """Set opt-in state and update the banner visibility."""
        if value == self._broadcast_opted_in:
            return
        self._broadcast_opted_in = value
        self._broadcast_banner.setVisible(value)
        if value:
            self._broadcast_banner.setText(
                f"📢  {_('MultiExec — receiving broadcast keystrokes')}"
            )
        else:
            self._broadcast_banner.setText("")
        self.broadcast_opt_in_changed.emit(value)

    def has_opt_in(self) -> bool:
        """Convenience: can this tab participate in broadcast?"""
        return self._connected and self._broadcast_opted_in

    # ── connection ────────────────────────────────────────────────────────────

    def _toggle_connection(self) -> None:
        if self._connected:
            self._disconnect()
        elif self.connect_button.text() == _("Cancel"):
            self._cancel_connect()
        else:
            self._connect()

    def _connect(self) -> None:
        if self._connect_thread is not None:
            return
        if not self._ensure_auth_material():
            return
        self._connect_cancelled = False
        self.connect_button.setText(_("Cancel"))
        self.connect_button.setEnabled(True)
        self.reconnect_button.setEnabled(False)
        self.trust_host_button.setEnabled(False)
        self.status_label.setText(_("● Connecting..."))
        self.status_label.setStyleSheet(_STATUS_CONNECTING)

        thread = QThread(self)
        worker = _SshConnectWorker(self.backend)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.output.connect(self._on_backend_output)
        worker.finished.connect(self._on_connect_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_connect_thread_finished)
        self._connect_thread = thread
        self._connect_worker = worker
        thread.start()

    def _ensure_auth_material(self) -> bool:
        """Prompt for a password when a profile has no usable auth material."""
        has_key = bool(self.profile.private_key_path)
        if self.profile.password or has_key or self.profile.use_ssh_agent:
            return True
        password, ok = QInputDialog.getText(
            self,
            _("SSH Password"),
            _("Enter password for {user}@{host}:").format(
                user=self.profile.username or self.profile.host,
                host=self.profile.host,
            ),
            QLineEdit.Password,
        )
        if not ok:
            return False
        self.profile.password = password or None
        return True

    @Slot(bytes)
    def _on_backend_output(self, data: bytes) -> None:
        self.terminal.feed(data.decode("utf-8", errors="replace"))

    @Slot(bool, str)
    def _on_connect_finished(self, success: bool, error: str) -> None:
        if self._connect_cancelled:
            self._connected = False
            self.connect_button.setEnabled(True)
            self.connect_button.setText(_("Connect"))
            self.status_label.setText(_("● Disconnected"))
            self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
            self.connection_status_changed.emit(False)
            return

        self.connect_button.setEnabled(True)
        if success:
            self._connected = True
            self.status_label.setText(_("● Connected"))
            self.status_label.setStyleSheet(_STATUS_CONNECTED)
            self.connect_button.setText(_("Disconnect"))
            self.reconnect_button.setEnabled(True)
            self.trust_host_button.setEnabled(False)
            self.sftp_button.setEnabled(True)
            self.snippet_button.setEnabled(True)
            self.sftp_attach_btn.setEnabled(True)
            self._enable_macro_buttons()
            self.connection_status_changed.emit(True)
            QTimer.singleShot(
                0,
                lambda: self.terminal.setFocus(Qt.OtherFocusReason),
            )
            QTimer.singleShot(150, self._wake_remote_prompt)
        else:
            self._connected = False
            self.status_label.setText(_("● Connection Failed"))
            self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
            self.connect_button.setText(_("Connect"))
            pending_host_key = self.backend.pending_host_key()
            if pending_host_key:
                self.trust_host_button.setEnabled(True)
                self.terminal.feed(
                    "\r\n*** Unknown host key: "
                    f"{pending_host_key.hostname} "
                    f"{pending_host_key.key_type} "
                    f"{pending_host_key.fingerprint_sha256}. "
                    "Trust this host key to continue. ***\r\n"
                )
                if self._confirm_trust_host_key(pending_host_key):
                    self._trust_pending_host_key(auto_reconnect=True)
            elif error:
                self.terminal.feed(f"\r\n*** {error} ***\r\n")
            self.connection_status_changed.emit(False)

    @Slot()
    def _on_connect_thread_finished(self) -> None:
        self._connect_thread = None
        self._connect_worker = None

    def _confirm_trust_host_key(self, prompt) -> bool:
        reply = QMessageBox.question(
            self,
            _("Trust SSH Host Key"),
            _(
                "The SSH host key for {host} is not trusted yet.\n\n"
                "Type: {key_type}\n"
                "Fingerprint: {fingerprint}\n\n"
                "Only trust it if this fingerprint is expected."
            ).format(
                host=prompt.hostname,
                key_type=prompt.key_type,
                fingerprint=prompt.fingerprint_sha256,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _trust_pending_host_key(self, auto_reconnect: bool = True) -> None:
        if self.backend.trust_pending_host_key():
            self.trust_host_button.setEnabled(False)
            self.status_label.setText(_("● Host Key Trusted"))
            self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
            if auto_reconnect:
                self.terminal.feed("\r\n*** Host key trusted. Connecting again. ***\r\n")
                QTimer.singleShot(0, self._connect)
            else:
                self.terminal.feed("\r\n*** Host key trusted. Connect again to start the session. ***\r\n")
        else:
            self.trust_host_button.setEnabled(False)

    def _cancel_connect(self) -> None:
        """Cancel an in-progress connection attempt."""
        self._connect_cancelled = True
        if self._connect_worker is not None:
            self._connect_worker.cancel()
        else:
            self._stop_connect_worker()
        self.backend.disconnect()
        self._connected = False
        self.connect_button.setEnabled(True)
        self.connect_button.setText(_("Connect"))
        self.status_label.setText(_("● Disconnected"))
        self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
        self.connection_status_changed.emit(False)

    def _on_key_pressed(self, text: str) -> None:
        self.backend.send(text)
        if self._macro_recording:
            self._macro_keys.append(text)

    def _wake_remote_prompt(self) -> None:
        """Send Enter once after login so quiet shells show a fresh prompt."""
        if self._connected:
            self.backend.send("\r")

    # ── macro recording ───────────────────────────────────────────────────────

    def _toggle_macro_recording(self) -> None:
        self._macro_recording = self.macro_record_btn.isChecked()
        if self._macro_recording:
            self._macro_keys = []
            self.macro_record_btn.setText("⏹")
            self.macro_record_btn.setStyleSheet(
                "QPushButton { color: #e05555; font-weight: bold; }"
            )
            self.macro_play_btn.setEnabled(False)
        else:
            self.macro_record_btn.setText("⏺")
            self.macro_record_btn.setStyleSheet("")
            self._last_macro = list(self._macro_keys)
            if self._last_macro:
                # Save as snippet
                name = f"Macro {len(self._macro_keys)} keys"
                content = "".join(self._last_macro)
                from openadmindesk.core.snippet_store import Snippet
                import time
                snippet = Snippet(
                    id=f"macro_{int(time.time())}", name=name,
                    content=content, language="macro"
                )
                self.snippet_store.add_snippet(snippet)
                self.macro_play_btn.setEnabled(True)

    def _play_macro(self) -> None:
        """Play back the last recorded macro."""
        if not self._last_macro or not self._connected:
            return
        for key in self._last_macro:
            self.backend.send(key)

    def _enable_macro_buttons(self) -> None:
        self.macro_record_btn.setEnabled(True)
        self.monitor_btn.setEnabled(True)
        if self._last_macro:
            self.macro_play_btn.setEnabled(True)

    # ── remote monitor ──────────────────────────────────────────────────────
    def _toggle_monitor(self) -> None:
        if not self._connected:
            return
        if self.monitor_btn.isChecked():
            self._start_monitor()
        else:
            self._stop_monitor()

    def _start_monitor(self) -> None:
        cmd = (
            "echo '===MON===';top -bn1 2>/dev/null|head -5;"
            "free -h 2>/dev/null|head -3;"
            "df -h / 2>/dev/null|tail -1;echo '===END==='\r"
        )
        self.backend.send(cmd)
        if not self._monitor_timer:
            self._monitor_timer = QTimer(self)
            self._monitor_timer.timeout.connect(lambda: self.backend.send(cmd))
        self._monitor_timer.start(10000)

    def _stop_monitor(self) -> None:
        if self._monitor_timer:
            self._monitor_timer.stop()

    def _on_reconnect(self) -> None:
        self._disconnect()
        self._connect()

    def _stop_connect_worker(self, wait_ms: int = 1000) -> None:
        if self._connect_thread is None:
            return
        self._connect_cancelled = True
        if self._connect_worker is not None:
            self._connect_worker.cancel()
        else:
            self.backend.disconnect()
        self._connect_thread.quit()
        self._connect_thread.wait(wait_ms)

    def _disconnect(self) -> None:
        if self.sftp_browser:
            self.sftp_browser.disconnect()
        self._stop_monitor()
        self.monitor_btn.setChecked(False)
        self.monitor_btn.setEnabled(False)
        self._stop_connect_worker()
        self.backend.disconnect()
        self._connected = False
        self.status_label.setText(_("● Disconnected"))
        self.sftp_button.setEnabled(False)
        self.sftp_attach_btn.setEnabled(False)
        self.sftp_detach_btn.setEnabled(False)
        self.sftp_close_btn.setEnabled(False)
        # Also close any attached SFTP panel
        if self.has_attached_sftp():
            self.close_attached_sftp()
        self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
        self.connect_button.setText(_("Connect"))
        self.reconnect_button.setEnabled(False)
        self.sftp_button.setEnabled(False)
        self.snippet_button.setEnabled(False)
        self.connection_status_changed.emit(False)

    # ── SFTP ──────────────────────────────────────────────────────────────────

    def _toggle_sftp_browser(self) -> None:
        self.sftp_button.setChecked(False)
        self.sftp_requested.emit(self.profile)

    # ── snippets ──────────────────────────────────────────────────────────────

    def _on_sftp_status(self, message: str) -> None:
        """Handle SFTP status messages without writing into terminal output."""
        self.status_label.setText(f"SFTP: {message}")

    def _on_sftp_closed(self) -> None:
        """Handle SFTP browser close from legacy embedded panel."""
        self._sftp_visible = False
        self.sftp_button.setChecked(False)
        if self.sftp_browser:
            self.sftp_browser.disconnect()
            self.sftp_browser.deleteLater()
            self.sftp_browser = None


    def _on_snippet_insert(self, snippet_id: str, _name: str) -> None:
        snippet = self.snippet_store.get_snippet(snippet_id)
        if snippet and self._connected:
            for line in snippet.content.split("\n"):
                self.backend.send(line + "\r")

    # ── terminal settings ──────────────────────────────────────────────────────

    def _terminal_context_menu(self, position) -> None:
        menu = QMenu()
        settings_action = QAction(_("⚙ Terminal Settings..."), self)
        settings_action.triggered.connect(self._show_terminal_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(_("Clear Terminal"), self.terminal.clear)
        menu.exec(self.terminal.mapToGlobal(position))

    def _show_terminal_settings(self) -> None:
        dlg = TerminalSettingsDialog(self.terminal.theme, self)
        if dlg.exec() == TerminalSettingsDialog.Accepted:
            new_theme = dlg.result_theme()
            self.terminal.set_theme(new_theme)
            # Save to profile for next time
            self.profile.terminal_theme = new_theme.name

    # ── attached SFTP panel ─────────────────────────────────────────────────

    def has_attached_sftp(self) -> bool:
        """Check if an attached SFTP panel is currently open."""
        return self._attached_sftp_browser is not None

    def open_attached_sftp(self) -> None:
        """Open an attached SFTP browser panel."""
        if self.has_attached_sftp():
            return
        
        if not self._connected:
            return
            
        # Create SFTP browser
        self._attached_sftp_browser = SftpFileBrowser(self.profile)
        
        # Add browser to the pre-existing layout
        self._attached_sftp_layout.addWidget(self._attached_sftp_browser)
        
        # Show the panel
        self._attached_sftp_panel.setVisible(True)
        
        # Enable/disable buttons
        self.sftp_attach_btn.setEnabled(False)
        self.sftp_detach_btn.setEnabled(True)
        self.sftp_close_btn.setEnabled(True)
        
        # Emit signal
        self.attached_sftp_opened.emit()

    def close_attached_sftp(self) -> None:
        """Close the attached SFTP panel."""
        if not self.has_attached_sftp():
            return
            
        # Remove browser from layout and clean up
        self._attached_sftp_layout.removeWidget(self._attached_sftp_browser)
        self._attached_sftp_browser.close()
        self._attached_sftp_browser.deleteLater()
        self._attached_sftp_browser = None
        
        # Hide the panel
        self._attached_sftp_panel.setVisible(False)
        
        # Enable/disable buttons
        self.sftp_attach_btn.setEnabled(True)
        self.sftp_detach_btn.setEnabled(False)
        self.sftp_close_btn.setEnabled(False)
        
        # Emit signal
        self.attached_sftp_closed.emit()

    def detach_attached_sftp(self) -> None:
        """Detach the attached SFTP panel to a dedicated tab."""
        if not self.has_attached_sftp():
            return
            
        # Create a new SFTP browser for the dedicated tab
        dedicated_browser = SftpFileBrowser(self.profile)
        
        # Copy current directory if possible
        if hasattr(self._attached_sftp_browser, '_current_path'):
            current_path = self._attached_sftp_browser._current_path
            dedicated_browser._navigate_to(current_path)
        
        # Emit signal to open as dedicated tab
        self.sftp_requested.emit(self.profile)
        
        # Close the attached panel
        self.close_attached_sftp()

    # ── cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._connected or self._connect_thread is not None:
            self._disconnect()
        self.tab_closed.emit()
        event.accept()
