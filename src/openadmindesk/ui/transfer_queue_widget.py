"""Transfer queue widget — displays and controls queued SFTP transfers."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from typing import Optional

from openadmindesk.core.transfer_queue import (
    TransferDirection,
    TransferJob,
    TransferQueue,
    TransferStatus,
)
from openadmindesk.core.l10n import _


class TransferQueueWidget(QWidget):
    """Widget that displays and controls the transfer queue.

    Shows all jobs with name, direction, progress bar, status, and action buttons.
    Polls the TransferQueue for state changes via a timer.
    """

    job_cancelled = Signal(str)
    job_retried = Signal(str)
    clear_requested = Signal()
    queue_visibility_changed = Signal(bool)

    def __init__(self, queue: TransferQueue, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._queue = queue
        self._visible_jobs: list[str] = []  # tracked job IDs for UI
        self._setup_ui()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._refresh_table)
        self._poll_timer.start(500)  # refresh every 500ms

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        title = QLabel(_("Transfer Queue"))
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        header.addWidget(title)
        header.addStretch()

        self._clear_btn = QPushButton(_("Clear Completed"))
        self._clear_btn.clicked.connect(self._on_clear)
        header.addWidget(self._clear_btn)
        layout.addLayout(header)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            _("File"),
            _("Direction"),
            _("Progress"),
            _("Status"),
            _("Actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 160)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { font-size: 12px; } "
            "QTableWidget::item { padding: 2px 4px; }"
        )
        layout.addWidget(self._table)

        # Status bar
        self._status_label = QLabel(_("No active transfers"))
        self._status_label.setStyleSheet("color: #969696; font-size: 11px; padding: 2px 6px;")
        layout.addWidget(self._status_label)

        self.setMinimumHeight(200)

    # ── public API ──────────────────────────────────────────────────────────

    def active_count(self) -> int:
        """Number of jobs that are queued or running."""
        return self._queue.active_count()

    # ── slots ───────────────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        """Poll queue state and refresh the table."""
        jobs = self._queue.all_jobs()
        if not jobs:
            if self._table.rowCount() > 0:
                self._table.setRowCount(0)
                self._visible_jobs.clear()
                self._status_label.setText(_("No active transfers"))
                self.queue_visibility_changed.emit(False)
            return

        self.queue_visibility_changed.emit(True)
        active = self._queue.active_count()
        self._status_label.setText(
            _("{} active / {} total").format(active, len(jobs))
        )

        # Rebuild rows to match current job list
        job_ids = [j.id for j in jobs]
        if job_ids != self._visible_jobs:
            self._visible_jobs = job_ids
            self._table.setRowCount(len(jobs))
            for row, job in enumerate(jobs):
                self._populate_row(row, job)
        else:
            # Update progress and status for visible jobs
            for row, job in enumerate(jobs):
                self._update_row(row, job)

    def _populate_row(self, row: int, job: TransferJob) -> None:
        """Fill a table row for a job."""
        # File name
        name_item = QTableWidgetItem(job.display_name)
        name_item.setData(Qt.UserRole, job.id)
        self._table.setItem(row, 0, name_item)

        # Direction
        dir_text = "↑" if job.direction == TransferDirection.UPLOAD else "↓"
        dir_item = QTableWidgetItem(dir_text)
        dir_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 1, dir_item)

        # Progress bar widget
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(job.progress_pct))
        progress_bar.setTextVisible(True)
        self._table.setCellWidget(row, 2, progress_bar)

        # Status
        status_text = self._status_text(job)
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 3, status_item)

        # Action buttons
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 0, 2, 0)
        actions_layout.setSpacing(4)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.setFixedHeight(24)
        cancel_btn.clicked.connect(lambda checked, jid=job.id: self._cancel(jid))
        cancel_btn.setEnabled(job.cancel_allowed())
        actions_layout.addWidget(cancel_btn)

        retry_btn = QPushButton(_("Retry"))
        retry_btn.setFixedHeight(24)
        retry_btn.clicked.connect(lambda checked, jid=job.id: self._retry(jid))
        retry_btn.setEnabled(job.retry_allowed())
        actions_layout.addWidget(retry_btn)

        actions_layout.addStretch()
        self._table.setCellWidget(row, 4, actions_widget)

    def _update_row(self, row: int, job: TransferJob) -> None:
        """Update progress and status for an existing row."""
        # Update progress bar
        progress_bar = self._table.cellWidget(row, 2)
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(int(job.progress_pct))

        # Update status text
        status_text = self._status_text(job)
        status_item = self._table.item(row, 3)
        if status_item:
            status_item.setText(status_text)

        # Update action button states
        actions_widget = self._table.cellWidget(row, 4)
        if actions_widget:
            buttons = actions_widget.findChildren(QPushButton)
            for btn in buttons:
                if btn.text() == _("Cancel"):
                    btn.setEnabled(job.cancel_allowed())
                elif btn.text() == _("Retry"):
                    btn.setEnabled(job.retry_allowed())

    def _status_text(self, job: TransferJob) -> str:
        """Human-readable status text with optional error."""
        if job.status == TransferStatus.QUEUED:
            return _("Queued")
        elif job.status == TransferStatus.RUNNING:
            return _("Running...")
        elif job.status == TransferStatus.DONE:
            return _("Done")
        elif job.status == TransferStatus.FAILED:
            return _("Failed") + (f": {job.error}" if job.error else "")
        elif job.status == TransferStatus.CANCELLED:
            return _("Cancelled")
        return job.status.value

    def _cancel(self, job_id: str) -> None:
        self._queue.cancel_job(job_id)
        self.job_cancelled.emit(job_id)

    def _retry(self, job_id: str) -> None:
        self._queue.retry_job(job_id)
        self.job_retried.emit(job_id)

    def _on_clear(self) -> None:
        removed = self._queue.clear_completed()
        if removed > 0:
            self.clear_requested.emit()

    def closeEvent(self, event) -> None:
        self._poll_timer.stop()
        super().closeEvent(event)
