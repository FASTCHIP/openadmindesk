"""SFTP file browser UI."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem,
    QToolBar, QToolButton,
    QPushButton, QInputDialog, QMessageBox,
    QLabel, QLineEdit, QFileDialog, QMenu,
    QDialog, QFormLayout, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor
try:
    from PySide6.QtGui import QAction  # PySide6 >= 6.11
except ImportError:
    from PySide6.QtWidgets import QAction  # PySide6 < 6.11
from typing import Optional, List

from openadmindesk.core.sftp_backend import SftpBackend
from openadmindesk.core.remote_file import RemoteFile, FileType
from openadmindesk.core.profile import Profile
from openadmindesk.core.l10n import _
from openadmindesk.core.settings import AppSettings
from openadmindesk.core.transfer_queue import (
    ConflictResolution,
    TransferDirection,
    TransferJob,
    TransferQueue,
)
from openadmindesk.core.remote_edit_safety import (
    EditConflict,
    check_edit_safe,
    check_remote_conflict,
    make_snapshot,
)
from openadmindesk.ui.transfer_queue_widget import TransferQueueWidget
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid


class DropTreeWidget(QTreeWidget):
    """A tree widget that accepts file drops from the system."""
    files_dropped = Signal(list)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Note: setAcceptDrops(True) must be set, but we add it after
        # the tree is fully set up to avoid navigation issues
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
    def keyPressEvent(self, event) -> None:
        """Enter opens dir, Backspace goes up."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            items = self.selectedItems()
            if items:
                data = items[0].data(0, Qt.UserRole)
                if isinstance(data, RemoteFile) and data.file_type == FileType.DIRECTORY:
                    browser = self._browser()
                    if browser:
                        browser._navigate_to(data.path)
                    return
        elif event.key() == Qt.Key_Backspace:
            browser = self._browser()
            if browser:
                browser._go_up()
                return
        super().keyPressEvent(event)

    def _browser(self):
        """Find the parent SftpFileBrowser widget."""
        w = self.parent()
        while w:
            if hasattr(w, '_load_directory') and hasattr(w, '_go_up'):
                return w
            w = w.parent()
        return None


class SftpConnectionWorker(QThread):
    """Worker thread for SFTP connection to avoid UI blocking."""

    connected = Signal(bool)

    def __init__(self, backend: SftpBackend, profile: Profile) -> None:
        super().__init__()
        self.backend = backend
        self.profile = profile
        self._cancelled = False

    def run(self) -> None:
        result = self.backend.connect(
            host=self.profile.host,
            port=self.profile.port,
            username=self.profile.username,
            password=self.profile.password,
            private_key_path=self.profile.private_key_path,
        )
        if self._cancelled:
            self.backend.disconnect()
            result = False
        self.connected.emit(result)

    def cancel(self) -> None:
        self._cancelled = True
        self.backend.disconnect()


class SftpListDirectoryWorker(QThread):
    """Worker thread for directory listing to keep SFTP I/O off the UI thread."""

    loaded = Signal(list, str, object)
    failed = Signal(str)

    def __init__(self, backend: SftpBackend, path: str, parent_item=None) -> None:
        super().__init__()
        self.backend = backend
        self.path = path
        self.parent_item = parent_item

    def run(self) -> None:
        try:
            self.loaded.emit(
                self.backend.list_directory(self.path),
                self.path,
                self.parent_item,
            )
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.failed.emit(str(exc))


class SftpFileBrowser(QWidget):
    """SFTP file browser UI."""
    
    # Signals
    file_selected = Signal(str)
    directory_changed = Signal(str)
    status_message = Signal(str)
    browser_closed = Signal()
    
    def __init__(self, profile: Profile, parent: Optional[QWidget] = None,
                 queue: Optional[TransferQueue] = None,
                 settings: Optional[AppSettings] = None) -> None:
        """Initialize the SFTP file browser.
        
        Args:
            profile: SSH profile with connection parameters
            parent: Parent widget
            queue: Shared TransferQueue (created if not given)
            settings: AppSettings (defaults used if not given)
        """
        super().__init__(parent)
        self.profile = profile
        self._app_settings = settings or AppSettings()
        self.sftp_backend = SftpBackend()
        self.current_path = self._app_settings.sftp_default_path
        self._history = [self.current_path]
        self._history_index = 0
        self._show_hidden = self._app_settings.sftp_show_hidden_files
        self._connected = False
        self._worker: Optional[SftpConnectionWorker] = None
        self._list_worker: Optional[SftpListDirectoryWorker] = None
        self._child_workers: list[SftpListDirectoryWorker] = []

        # Transfer queue
        if queue is None:
            queue = TransferQueue()
            queue.set_upload_fn(
                lambda local, remote, cb: self.sftp_backend.upload_file(local, remote, cb)
            )
            queue.set_download_fn(
                lambda remote, local, cb: self.sftp_backend.download_file(remote, local, cb)
            )
            queue.start()
        self._queue = queue
        self._queue_showing = False

        self._setup_ui()
        self._connect_to_sftp()
    
    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ── Header with path + close ────────────────────────────────────
        header = QHBoxLayout()
        
        self.path_label = QLabel("📁")
        self.path_label.setStyleSheet("color: #007acc; font-size: 13px; font-weight: bold;")
        header.addWidget(self.path_label)

        self.path_input = QLineEdit("/")
        self.path_input.setPlaceholderText(_("Remote path"))
        self.path_input.returnPressed.connect(self._navigate_from_path_input)
        header.addWidget(self.path_input, 1)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { border: none; font-size: 14px; color: #e05555; } "
            "QPushButton:hover { background: #e05555; color: white; border-radius: 3px; }"
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)
        
        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        self.back_btn = QToolButton()
        self.back_btn.setText("←")
        self.back_btn.setToolTip(_("Back"))
        self.back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(self.back_btn)

        self.forward_btn = QToolButton()
        self.forward_btn.setText("→")
        self.forward_btn.setToolTip(_("Forward"))
        self.forward_btn.clicked.connect(self._go_forward)
        toolbar.addWidget(self.forward_btn)

        refresh_btn = QToolButton()
        refresh_btn.setText("⟳ Refresh")
        refresh_btn.clicked.connect(self._refresh_directory)
        toolbar.addWidget(refresh_btn)
        
        up_btn = QToolButton()
        up_btn.setText("⬆ Up")
        up_btn.clicked.connect(self._go_up)
        toolbar.addWidget(up_btn)
        
        root_btn = QToolButton()
        root_btn.setText("/ Root")
        root_btn.clicked.connect(lambda: self._navigate_to("/"))
        toolbar.addWidget(root_btn)

        home_btn = QToolButton()
        home_btn.setText("~ Home")
        home_btn.clicked.connect(lambda: self._navigate_to("~"))
        toolbar.addWidget(home_btn)

        self.hidden_btn = QToolButton()
        self.hidden_btn.setText("Hidden")
        self.hidden_btn.setCheckable(True)
        self.hidden_btn.setChecked(self._app_settings.sftp_show_hidden_files)
        self.hidden_btn.setToolTip(_("Show hidden files"))
        self.hidden_btn.toggled.connect(self._set_show_hidden)
        toolbar.addWidget(self.hidden_btn)
        
        toolbar.addSeparator()
        
        mkdir_btn = QToolButton()
        mkdir_btn.setText("📁 New Dir")
        mkdir_btn.clicked.connect(self._create_directory)
        toolbar.addWidget(mkdir_btn)
        
        upload_btn = QToolButton()
        upload_btn.setText("↑ Upload")
        upload_btn.clicked.connect(self._upload_file)
        toolbar.addWidget(upload_btn)
        
        toolbar.addSeparator()
        
        self.queue_btn = QToolButton()
        self.queue_btn.setText("📋 Queue")
        self.queue_btn.setCheckable(True)
        self.queue_btn.setToolTip(_("Show transfer queue"))
        self.queue_btn.toggled.connect(self._toggle_queue)
        toolbar.addWidget(self.queue_btn)
        
        layout.addWidget(toolbar)
        
        # ── Transfer queue panel (initially hidden) ──────────────────────
        self._queue_widget = TransferQueueWidget(self._queue)
        self._queue_widget.setVisible(False)
        self._queue_widget.queue_visibility_changed.connect(self._on_queue_activity)
        layout.addWidget(self._queue_widget)
        
        # ── File tree ────────────────────────────────────────────────────
        self.file_tree = DropTreeWidget()
        self.file_tree.files_dropped.connect(self._on_files_dropped)
        self.file_tree.setHeaderLabels([_("Name"), _("Size"), _("Type"), _("Perm"), _("Modified")])
        self.file_tree.setColumnWidth(0, 320)
        self.file_tree.setColumnWidth(1, 90)
        self.file_tree.setColumnWidth(2, 80)
        self.file_tree.setColumnWidth(3, 80)
        self.file_tree.setColumnWidth(4, 170)
        self.file_tree.setAlternatingRowColors(False)
        self.file_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.file_tree.setUniformRowHeights(True)
        tree_font_size = self._app_settings.sftp_tree_font_size
        self.file_tree.setStyleSheet(
            f"QTreeWidget {{ font-size: {tree_font_size}px; background-color: #1e1e1e; "
            "color: #d4d4d4; border: 0px; }} "
            "QHeaderView::section { background-color: #2d2d30; color: #d4d4d4; "
            "padding: 5px; border: 0px; font-weight: bold; } "
            "QTreeWidget::item:selected { background-color: #094771; color: #ffffff; } "
        )
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_tree.itemExpanded.connect(self._on_item_expanded)
        self.file_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.file_tree.setAcceptDrops(True)
        self.file_tree.setEnabled(True)
        self.file_tree.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.file_tree)
        
        # ── Status ───────────────────────────────────────────────────────
        self.connection_label = QLabel("Connecting...")
        self.connection_label.setStyleSheet("color: #969696; font-size: 11px; padding: 2px 6px;")
        layout.addWidget(self.connection_label)
        self.setMinimumSize(400, 300)
        self._sync_path_widgets()
    
    def _connect_to_sftp(self) -> None:
        """Connect to SFTP server in background."""
        if self._worker is not None and self._worker.isRunning():
            return
        self.connection_label.setText("Connecting...")
        self.connection_label.setStyleSheet(
            "color: #dcaa3a; font-weight: bold; font-size: 12px;"
        )

        self._worker = SftpConnectionWorker(self.sftp_backend, self.profile)
        self._worker.connected.connect(self._on_connection_result)
        self._worker.finished.connect(self._on_connection_worker_finished)
        self._worker.start()

    def _on_connection_worker_finished(self) -> None:
        self._worker = None

    def _on_connection_result(self, success: bool) -> None:
        """Handle SFTP connection result."""
        self._connected = success
        if success:
            self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet(
                "color: #4ec94e; font-weight: bold; font-size: 12px;"
            )
            self.status_message.emit("SFTP connected")
            self._load_directory()
        else:
            self.connection_label.setText("Disconnected")
            self.connection_label.setStyleSheet(
                "color: #e05555; font-weight: bold; font-size: 12px;"
            )
            self.status_message.emit("SFTP connection failed")

    def reconnect(self) -> None:
        """Reconnect to SFTP server."""
        self.disconnect()
        self._connect_to_sftp()

    def disconnect(self) -> None:
        """Disconnect from SFTP server."""
        self._stop_workers()
        if self._connected:
            self.sftp_backend.disconnect()
        self._connected = False
        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet("color: #969696; font-size: 12px;")
        self.file_tree.clear()

    def _stop_workers(self, wait_ms: int = 1000) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
            self._worker.wait(wait_ms)
        if self._list_worker is not None and self._list_worker.isRunning():
            self._list_worker.quit()
            self._list_worker.wait(wait_ms)
        for worker in list(self._child_workers):
            if worker.isRunning():
                worker.quit()
                worker.wait(wait_ms)
        self._child_workers.clear()

    def _load_directory(self) -> None:
        """Load current directory contents."""
        if not self._connected:
            return
        if self._list_worker is not None and self._list_worker.isRunning():
            return
        self._list_worker = SftpListDirectoryWorker(
            self.sftp_backend,
            self.current_path,
        )
        self._list_worker.loaded.connect(self._on_directory_loaded)
        self._list_worker.failed.connect(
            lambda error: self._show_status(f"Failed to load directory: {error}")
        )
        self._list_worker.finished.connect(self._on_list_worker_finished)
        self._list_worker.start()

    def _on_directory_loaded(self, files: list[RemoteFile], path: str, parent_item=None) -> None:
        if parent_item is None:
            self._update_file_list(files)
            self.current_path = path
            self._sync_path_widgets()
            return
        if not self._is_tree_item_alive(parent_item):
            return
        self._populate_child_directory(parent_item, files)

    def _on_list_worker_finished(self) -> None:
        self._list_worker = None

    def _show_status(self, message: str) -> None:
        self.connection_label.setText(message)
        self.status_message.emit(message)

    def _directory_item(self, file: RemoteFile) -> QTreeWidgetItem:
        item = self._file_item(file)
        item.addChild(QTreeWidgetItem([_("Loading..."), "", "", "", ""]))
        item.setData(0, Qt.UserRole + 1, False)
        return item

    def _file_item(self, file: RemoteFile) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        if file.file_type == FileType.DIRECTORY:
            name = f"[D] {file.name}"
            type_label = "Folder"
        elif file.file_type == FileType.LINK:
            name = f"[L] {file.name}"
            type_label = "Link"
        elif file.file_type == FileType.FILE:
            name = f"    {file.name}"
            type_label = "File"
        else:
            name = file.name
            type_label = "Other"
        item.setText(0, name)
        item.setText(1, self._format_size(file.size))
        item.setText(2, type_label)
        item.setText(3, self._format_permissions(file.permissions))
        item.setText(4, self._format_modified(file.modified_at))
        item.setData(0, Qt.UserRole, file)
        if file.file_type == FileType.DIRECTORY:
            item.setForeground(0, QColor("#8ab4f8"))
        elif file.file_type == FileType.LINK:
            item.setForeground(0, QColor("#c586c0"))
        else:
            item.setForeground(0, QColor("#d4d4d4"))
        return item

    def _update_file_list(self, files: List[RemoteFile]) -> None:
        """Update the file tree with directory contents."""
        self.file_tree.clear()
        files = self._filter_files(files)

        if self.current_path != "/":
            parent_item = QTreeWidgetItem(["[D] ..", "", "Folder", "", ""])
            parent_item.setData(0, Qt.UserRole, "..")
            parent_item.setForeground(0, QColor("#8ab4f8"))
            self.file_tree.addTopLevelItem(parent_item)

        for file in self._sort_files(files):
            item = (
                self._directory_item(file)
                if file.file_type == FileType.DIRECTORY
                else self._file_item(file)
            )
            self.file_tree.addTopLevelItem(item)

    def _filter_files(self, files: List[RemoteFile]) -> List[RemoteFile]:
        if self._show_hidden:
            return files
        return [file for file in files if not file.name.startswith(".")]

    def _sort_files(self, files: List[RemoteFile]) -> List[RemoteFile]:
        return sorted(
            files,
            key=lambda item: (
                item.file_type != FileType.DIRECTORY,
                item.name.casefold(),
            ),
        )

    def _populate_child_directory(
        self,
        parent_item: QTreeWidgetItem,
        files: List[RemoteFile],
    ) -> None:
        if not self._is_tree_item_alive(parent_item):
            return
        parent_item.takeChildren()
        for file in self._sort_files(files):
            child = (
                self._directory_item(file)
                if file.file_type == FileType.DIRECTORY
                else self._file_item(file)
            )
        parent_item.addChild(child)
        parent_item.setData(0, Qt.UserRole + 1, True)

    def _is_tree_item_alive(self, item: QTreeWidgetItem) -> bool:
        """Return False when a queued worker references a deleted Qt item."""
        try:
            item.treeWidget()
            item.parent()
            return True
        except RuntimeError:
            return False

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.UserRole)
        loaded = bool(item.data(0, Qt.UserRole + 1))
        if not isinstance(data, RemoteFile) or data.file_type != FileType.DIRECTORY:
            return
        if loaded or not self._connected:
            return
        worker = SftpListDirectoryWorker(self.sftp_backend, data.path, item)
        worker.loaded.connect(self._on_directory_loaded)
        worker.failed.connect(
            lambda error: self._show_status(f"Failed to load directory: {error}")
        )
        worker.finished.connect(lambda w=worker: self._on_child_worker_finished(w))
        self._child_workers.append(worker)
        worker.start()

    def _on_child_worker_finished(self, worker: SftpListDirectoryWorker) -> None:
        if worker in self._child_workers:
            self._child_workers.remove(worker)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024*1024):.1f} MB"
        else:
            return f"{size_bytes / (1024*1024*1024):.1f} GB"

    def _format_permissions(self, permissions) -> str:
        """Normalize backend permission values for compact table display."""
        if permissions in (None, ""):
            return ""
        try:
            return oct(int(permissions))[-3:]
        except (TypeError, ValueError):
            return str(permissions)

    def _format_modified(self, modified_at) -> str:
        """Render timestamps as readable local date/time instead of raw epoch."""
        if modified_at in (None, ""):
            return ""
        if isinstance(modified_at, datetime):
            return modified_at.strftime("%Y-%m-%d %H:%M")
        try:
            value = float(modified_at)
        except (TypeError, ValueError):
            return str(modified_at)
        if value <= 0:
            return ""
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    
    def _refresh_directory(self) -> None:
        """Refresh current directory."""
        self._load_directory()
    
    def _go_up(self) -> None:
        """Navigate to parent directory."""
        if self.current_path in {"/", "~"}:
            return
        parts = self.current_path.rstrip("/").split("/")
        parent = "/".join(parts[:-1]) or "/" if len(parts) > 1 else "/"
        self._navigate_to(parent)

    def _go_back(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._navigate_to(
            self._history[self._history_index],
            record_history=False,
        )

    def _go_forward(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._navigate_to(
            self._history[self._history_index],
            record_history=False,
        )

    def _navigate_from_path_input(self) -> None:
        self._navigate_to(self.path_input.text())

    def _navigate_to(self, path: str, record_history: bool = True) -> None:
        """Navigate to a specific path."""
        normalized = self._normalize_path(path)
        if record_history and normalized != self.current_path:
            self._history = self._history[: self._history_index + 1]
            self._history.append(normalized)
            self._history_index = len(self._history) - 1
        self.current_path = normalized
        self._sync_path_widgets()
        self._load_directory()
        self.directory_changed.emit(self.current_path)

    def _normalize_path(self, path: str) -> str:
        path = (path or "/").strip()
        if path == "~":
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        while "//" in path:
            path = path.replace("//", "/")
        return path.rstrip("/") or "/"

    def _sync_path_widgets(self) -> None:
        self.path_input.setText(self.current_path)
        self.back_btn.setEnabled(self._history_index > 0)
        self.forward_btn.setEnabled(
            self._history_index < len(self._history) - 1
        )

    def _set_show_hidden(self, checked: bool) -> None:
        self._show_hidden = checked
        self._refresh_directory()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double click on item."""
        data = item.data(0, Qt.UserRole)
        
        if data == "..":
            self._go_up()
            return
        
        if isinstance(data, RemoteFile):
            if data.file_type == FileType.DIRECTORY:
                self._navigate_to(data.path)
            else:
                self.file_selected.emit(data.path)
                action = self._app_settings.sftp_double_click_action
                if action == "download":
                    self._download_selected_file(item)
                elif action == "open":
                    # Open in system: download to temp and xdg-open
                    self._edit_file(item)  # same flow as edit for now
                else:
                    # Default: edit
                    self._edit_file(item)
    
    # ── transfer queue ──────────────────────────────────────────────────────

    def _toggle_queue(self, visible: bool) -> None:
        """Show or hide the transfer queue panel."""
        self._queue_widget.setVisible(visible)
        self._queue_showing = visible

    def _on_queue_activity(self, has_jobs: bool) -> None:
        """Update queue button when jobs appear or disappear."""
        self.queue_btn.setChecked(self._queue_showing or has_jobs)
        if has_jobs and not self._queue_showing:
            self.queue_btn.setStyleSheet(
                "QToolButton { color: #dcaa3a; font-weight: bold; }"
            )
        else:
            self.queue_btn.setStyleSheet("")

    def _confirm_destination_conflict(
        self, local_path: str, remote_path: str, is_upload: bool
    ) -> ConflictResolution:
        """Ask user how to handle destination file conflict."""
        existing = self.sftp_backend.get_file_info(remote_path)
        if existing is None:
            return ConflictResolution.OVERWRITE
        # Check if local file exists for downloads
        if not is_upload and not os.path.exists(local_path):
            return ConflictResolution.OVERWRITE

        msg = QMessageBox(self)
        msg.setWindowTitle(_("Destination file exists"))
        if is_upload:
            msg.setText(
                _("Remote file already exists:\n{}\n\n"
                  "What do you want to do?").format(remote_path)
            )
        else:
            msg.setText(
                _("Local file already exists:\n{}\n\n"
                  "What do you want to do?").format(local_path)
            )
        overwrite_btn = msg.addButton(_("Overwrite"), QMessageBox.AcceptRole)
        rename_btn = msg.addButton(_("Rename"), QMessageBox.ActionRole)
        skip_btn = msg.addButton(_("Skip"), QMessageBox.RejectRole)
        msg.setDefaultButton(overwrite_btn)
        msg.exec()

        if msg.clickedButton() == rename_btn:
            return ConflictResolution.RENAME
        elif msg.clickedButton() == skip_btn:
            return ConflictResolution.SKIP
        return ConflictResolution.OVERWRITE

    def _queue_upload(self, local_path: str, remote_path: str) -> None:
        """Queue an upload job with conflict check."""
        if not self._connected:
            return

        # Check destination conflict
        resolution = self._confirm_destination_conflict(
            local_path, remote_path, is_upload=True
        )
        if resolution == ConflictResolution.SKIP:
            self.status_message.emit(
                _("Skipped upload of {}").format(os.path.basename(local_path))
            )
            return

        total_size = os.path.getsize(local_path)
        job = TransferJob(
            id=f"up_{uuid.uuid4().hex[:8]}",
            direction=TransferDirection.UPLOAD,
            local_path=local_path,
            remote_path=remote_path,
            size_bytes=total_size,
            conflict_resolution=resolution,
        )
        self._queue.add_job(job)
        self.status_message.emit(
            _("Queued upload: {}").format(os.path.basename(local_path))
        )

    def _queue_download(self, remote_path: str, local_path: str, size_bytes: int) -> None:
        """Queue a download job with conflict check."""
        if not self._connected:
            return

        # Check destination conflict
        resolution = self._confirm_destination_conflict(
            local_path, remote_path, is_upload=False
        )
        if resolution == ConflictResolution.SKIP:
            self.status_message.emit(
                _("Skipped download of {}").format(os.path.basename(remote_path))
            )
            return

        job = TransferJob(
            id=f"dl_{uuid.uuid4().hex[:8]}",
            direction=TransferDirection.DOWNLOAD,
            local_path=local_path,
            remote_path=remote_path,
            size_bytes=size_bytes,
            conflict_resolution=resolution,
        )
        self._queue.add_job(job)
        self.status_message.emit(
            _("Queued download: {}").format(os.path.basename(remote_path))
        )

    def _create_directory(self) -> None:
        """Create a new directory."""
        if not self._connected:
            return
        
        name, ok = QInputDialog.getText(self, _("Create Directory"), "Enter directory name:")
        if ok and name:
            full_path = f"{self.current_path.rstrip('/')}/{name.lstrip('/')}"
            success = self.sftp_backend.make_directory(full_path)
            if success:
                self._load_directory()
                self.status_message.emit(f"Directory '{name}' created")
            else:
                QMessageBox.critical(self, "Error", f"Failed to create directory '{name}'")
    
    def _on_files_dropped(self, paths: list) -> None:
        """Handle files dropped from the system onto the SFTP tree."""
        if not self._connected:
            return
        for local_path in paths:
            remote_path = f"{self.current_path.rstrip('/')}/{os.path.basename(local_path)}"
            self._queue_upload(local_path, remote_path)

    def _upload_file(self) -> None:
        """Upload a file to current directory (queued)."""
        if not self._connected:
            return
        
        file_path, selected_filter = QFileDialog.getOpenFileName(self, _("Select File to Upload"))
        if not file_path:
            return

        remote_path = f"{self.current_path.rstrip('/')}/{os.path.basename(file_path)}"
        self._queue_upload(file_path, remote_path)
    
    def _download_selected_file(self, item: QTreeWidgetItem) -> None:
        """Download the selected file (queued)."""
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, RemoteFile) or data.file_type == FileType.DIRECTORY:
            return
        
        save_path, selected_filter = QFileDialog.getSaveFileName(self, _("Save File"), data.name)
        if not save_path:
            return

        self._queue_download(data.path, save_path, data.size)
    
    def _delete_selected_file(self, item: QTreeWidgetItem) -> None:
        """Delete the selected file(s) or directory(ies)."""
        items = self.file_tree.selectedItems()
        if not items:
            items = [item]
        if not items:
            return

        names = ", ".join(i.data(0, Qt.UserRole).name for i in items[:5] if i.data(0, Qt.UserRole))
        if len(items) > 5:
            names += f" +{len(items) - 5} more"

        reply = QMessageBox.question(
            self, _("Delete"),
            f"Are you sure you want to delete {len(items)} item(s):\n{names}?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            for item_to_delete in items:
                data = item_to_delete.data(0, Qt.UserRole)
                if isinstance(data, RemoteFile):
                    self.sftp_backend.remove_file(data.path)
            self._load_directory()
            self.status_message.emit(f"Deleted {len(items)} item(s)")
    
    def _show_context_menu(self, position) -> None:
        """Show context menu for file items."""
        item = self.file_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        data = item.data(0, Qt.UserRole)
        
        if isinstance(data, RemoteFile):
            if data.file_type == FileType.DIRECTORY:
                open_action = QAction(_("Open"), self)
                open_action.triggered.connect(
                    lambda: self._navigate_to(data.path)
                )
                menu.addAction(open_action)
            else:
                download_action = QAction(_("Download"), self)
                download_action.triggered.connect(
                    lambda: self._download_selected_file(item)
                )
                menu.addAction(download_action)
                
                edit_action = QAction("✏ " + _("Edit"), self)
                edit_action.triggered.connect(
                    lambda: self._edit_file(item)
                )
                menu.addAction(edit_action)
            
            menu.addAction("🔒 " + _("Permissions..."), lambda: self._show_chmod(item))
            menu.addSeparator()
            
            delete_action = QAction(_("Delete"), self)
            delete_action.triggered.connect(
                lambda: self._delete_selected_file(item)
            )
            menu.addAction(delete_action)
        
        menu.exec(self.file_tree.mapToGlobal(position))

    def _show_chmod(self, item: QTreeWidgetItem) -> None:
        """Show chmod dialog for a file/directory."""
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, RemoteFile):
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Permissions — {data.name}")
        layout = QFormLayout(dlg)

        # Parse current permissions
        try:
            current = int(data.permissions, 8) if data.permissions else 0o644
        except (ValueError, TypeError):
            current = 0o644

        checks = {}
        for label, mask in [("Owner Read", 0o400), ("Owner Write", 0o200),
                            ("Owner Execute", 0o100),
                            ("Group Read", 0o040), ("Group Write", 0o020),
                            ("Group Execute", 0o010),
                            ("Other Read", 0o004), ("Other Write", 0o002),
                            ("Other Execute", 0o001)]:
            cb = QCheckBox(label)
            cb.setChecked(bool(current & mask))
            checks[mask] = cb
            layout.addRow(cb)

        octal_label = QLabel(f"Octal: {oct(current)[2:]:>03s}")
        layout.addRow(octal_label)

        # Update octal on checkbox change
        def update_octal():
            mode = sum(mask for mask, cb in checks.items() if cb.isChecked())
            octal_label.setText(f"Octal: {oct(mode)[2:]:>03s}")
        for cb in checks.values():
            cb.toggled.connect(update_octal)

        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton(_("Cancel"))
        ok.clicked.connect(lambda: self._apply_chmod(dlg, checks, data.path))
        cancel.clicked.connect(dlg.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addRow(buttons)

        dlg.exec()

    def _apply_chmod(self, dlg, checks: dict, path: str) -> None:
        mode = sum(mask for mask, cb in checks.items() if cb.isChecked())
        try:
            self.sftp_backend._sftp_client.chmod(path, mode)
            self._load_directory()
            self.status_message.emit(f"Permissions set to {oct(mode)[2:]}")
        except Exception:
            QMessageBox.critical(self, "Error", "Failed to change permissions")
        dlg.accept()

    def _edit_file(self, item: QTreeWidgetItem) -> None:
        """Download, open in editor, upload back on save — with conflict safety."""
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, RemoteFile) or data.file_type == FileType.DIRECTORY:
            return

        remote_path = data.path

        # ── binary / size guard ────────────────────────────────────────────
        safe, reason = check_edit_safe(remote_path, data.size)
        if not safe:
            reply = QMessageBox.question(
                self,
                _("Edit Warning"),
                f"{reason}.\n\n{_('Open anyway?')}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        else:
            reply = QMessageBox.question(
                self,
                _("Open Remote File"),
                _(
                    "Open {name} in your local editor?\n\n"
                    "OpenAdminDesk will download it to a temporary folder and "
                    "upload changes back after you save."
                ).format(name=data.name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        # ── capture remote stat snapshot BEFORE download ───────────────────
        remote_info = self.sftp_backend.get_file_info(remote_path)
        if remote_info is None:
            QMessageBox.critical(self, "Error", _("Failed to stat remote file"))
            return
        snapshot = make_snapshot(
            remote_path=remote_path,
            mtime=float(remote_info.modified_at) if remote_info.modified_at else None,
            size=remote_info.size,
        )

        # ── download to temp ───────────────────────────────────────────────
        local_dir = tempfile.mkdtemp(prefix="oad_edit_")
        local_path = os.path.join(local_dir, data.name)
        try:
            if not self.sftp_backend.download_file(remote_path, local_path):
                QMessageBox.critical(self, "Error", f"Failed to download {data.name}")
                return
        except Exception:
            shutil.rmtree(local_dir, ignore_errors=True)
            raise

        orig_mtime = os.path.getmtime(local_path)

        # ── open editor ────────────────────────────────────────────────────
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "xdg-open"))
        try:
            subprocess.Popen([editor, local_path], start_new_session=True)
        except Exception:
            try:
                subprocess.Popen(["xdg-open", local_path], start_new_session=True)
            except Exception:
                shutil.rmtree(local_dir, ignore_errors=True)
                return

        self.status_message.emit(f"Editing {data.name} — save to upload")

        # ── background watcher ─────────────────────────────────────────────
        def _watch() -> None:
            try:
                while True:
                    time.sleep(1)
                    try:
                        current_mtime = os.path.getmtime(local_path)
                    except OSError:
                        break  # file was deleted
                    if current_mtime == orig_mtime:
                        continue  # not saved yet

                    # File was saved — check for remote conflict
                    time.sleep(0.5)  # let the editor finish writing

                    # Re-stat remote
                    current_info = self.sftp_backend.get_file_info(remote_path)
                    if current_info is None:
                        # Remote disappeared
                        self.status_message.emit(
                            "⚠ Remote file deleted during editing"
                        )
                        break

                    current_mtime_f = (
                        float(current_info.modified_at)
                        if current_info.modified_at else None
                    )
                    conflict = check_remote_conflict(
                        snapshot,
                        current_mtime_f,
                        current_info.size,
                    )

                    if conflict == EditConflict.NO_CONFLICT:
                        # Safe to upload
                        if self.sftp_backend.upload_file(local_path, remote_path):
                            self.status_message.emit(
                                f"✅ {data.name} saved"
                            )
                        else:
                            self.status_message.emit(
                                f"❌ Failed to upload {data.name}"
                            )
                        break

                    # Conflict — prompt user
                    action = self._resolve_edit_conflict(
                        data.name, conflict, current_info
                    )
                    if action == "overwrite":
                        if self.sftp_backend.upload_file(local_path, remote_path):
                            self.status_message.emit(
                                f"✅ {data.name} saved (overwritten)"
                            )
                        else:
                            self.status_message.emit(
                                f"❌ Failed to upload {data.name}"
                            )
                        break
                    elif action == "save_as":
                        # Upload to a renamed remote path
                        base, ext = os.path.splitext(remote_path)
                        safe_path = f"{base}.conflict_copy{ext}"
                        if self.sftp_backend.upload_file(local_path, safe_path):
                            self.status_message.emit(
                                f"✅ Saved as {os.path.basename(safe_path)}"
                            )
                        else:
                            self.status_message.emit(
                                f"❌ Failed to save {data.name}"
                            )
                        break
                    else:  # cancel
                        self.status_message.emit(
                            f"⏹ Upload cancelled for {data.name}"
                        )
                        break
            finally:
                shutil.rmtree(local_dir, ignore_errors=True)

        threading.Thread(target=_watch, daemon=True).start()

    def _resolve_edit_conflict(
        self,
        name: str,
        conflict: EditConflict,
        current_info: RemoteFile,
    ) -> str:
        """Show a dialog asking how to handle a remote edit conflict.

        Returns 'overwrite', 'save_as', or 'cancel'.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle(_("Remote file changed"))

        if conflict == EditConflict.REMOTE_DELETED:
            msg.setText(
                _("The remote file '{}' was deleted during editing.").format(name)
            )
        else:
            msg.setText(
                _("The remote file '{}' was modified during editing.\n\n"
                  "Remote: mtime={}, size={}").format(
                    name,
                    str(current_info.modified_at or "?"),
                    current_info.size,
                )
            )

        msg.setInformativeText(
            _("What do you want to do with your local changes?")
        )

        overwrite_btn = msg.addButton(
            _("Overwrite"), QMessageBox.AcceptRole
        )
        save_as_btn = msg.addButton(
            _("Save As..."), QMessageBox.ActionRole
        )
        cancel_btn = msg.addButton(
            _("Cancel Upload"), QMessageBox.RejectRole
        )
        msg.setDefaultButton(cancel_btn)
        msg.exec()

        if msg.clickedButton() == overwrite_btn:
            return "overwrite"
        elif msg.clickedButton() == save_as_btn:
            return "save_as"
        return "cancel"

    def closeEvent(self, event) -> None:
        """Clean up on close — emit signal so parent can update state."""
        self.disconnect()
        self.browser_closed.emit()
        self.sftp_backend.close()
        event.accept()
