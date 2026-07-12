"""Local shell terminal tab — bash/cmd in-app."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QToolBar,
)
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from openadmindesk.core.local_shell_backend import LocalShellBackend
from openadmindesk.ui.terminal_widget import TerminalWidget
from openadmindesk.ui.terminal_theme import get_theme
from openadmindesk.ui.terminal_settings import TerminalSettingsDialog
from openadmindesk.core.l10n import _



class _LocalShellConnectWorker(QObject):
    """Starts the local shell outside the UI thread."""

    output = Signal(str)
    finished = Signal(bool)

    def __init__(self, backend: LocalShellBackend) -> None:
        super().__init__()
        self._backend = backend

    @Slot()
    def run(self) -> None:
        self.finished.emit(self._backend.connect(on_output=self.output.emit))

    @Slot()
    def cancel(self) -> None:
        self._backend.disconnect()

_STATUS_DISCONNECTED = "color: #e05555; font-weight: bold;"
_STATUS_CONNECTING = "color: #dcaa3a; font-weight: bold;"
_STATUS_CONNECTED = "color: #4ec94e; font-weight: bold;"


class LocalShellTab(QWidget):
    """Local shell terminal tab."""

    tab_closed = Signal()

    def __init__(self, shell_name: str = "bash") -> None:
        super().__init__()
        self._shell_name = shell_name
        self.backend = LocalShellBackend()
        self._connected = False
        self._connect_thread: QThread | None = None
        self._connect_worker: _LocalShellConnectWorker | None = None
        self._setup_ui()
        self._connect()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QToolBar()
        self.info_label = QLabel(f"💻  {self._shell_name}")
        toolbar.addWidget(self.info_label)
        toolbar.addSeparator()

        self.status_label = QLabel(_("● Disconnected"))
        self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
        toolbar.addWidget(self.status_label)
        toolbar.addSeparator()

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
        theme = get_theme("Dark")
        self.terminal.set_theme(theme)
        layout.addWidget(self.terminal)

    def _connect(self) -> None:
        if self._connect_thread is not None:
            return
        self.status_label.setText(_("● Connecting..."))
        self.status_label.setStyleSheet(_STATUS_CONNECTING)

        thread = QThread(self)
        worker = _LocalShellConnectWorker(self.backend)
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

    @Slot(str)
    def _on_backend_output(self, data: str) -> None:
        self.terminal.feed(data)
        self.terminal._reset_scroll_position()

    @Slot(bool)
    def _on_connect_finished(self, success: bool) -> None:
        if success:
            self._connected = True
            self.status_label.setText(_("● Connected"))
            self.status_label.setStyleSheet(_STATUS_CONNECTED)
            self.reconnect_button.setEnabled(True)
        else:
            self._connected = False
            self.status_label.setText(_("● Connection Failed"))
            self.status_label.setStyleSheet(_STATUS_DISCONNECTED)
            self.reconnect_button.setEnabled(False)

    @Slot()
    def _on_connect_thread_finished(self) -> None:
        self._connect_thread = None
        self._connect_worker = None

    def _stop_connect_worker(self, wait_ms: int = 1000) -> None:
        if self._connect_thread is None:
            return
        if self._connect_worker is not None:
            self._connect_worker.cancel()
        else:
            self.backend.disconnect()
        self._connect_thread.quit()
        self._connect_thread.wait(wait_ms)

    def _on_key_pressed(self, text: str) -> None:
        self.backend.send(text)

    def _on_reconnect(self) -> None:
        self._stop_connect_worker()
        self.backend.disconnect()
        self._connected = False
        self._connect()

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

    def closeEvent(self, event) -> None:
        self._stop_connect_worker()
        self.backend.disconnect()
        self.tab_closed.emit()
        event.accept()
