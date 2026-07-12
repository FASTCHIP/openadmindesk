"""Multi-execution panel — visible target selection for broadcast keystrokes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from typing import List, Optional

from openadmindesk.core.l10n import _
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab


class MultiExecPanel(QWidget):
    """Panel listing connected SSH tabs with opt-in checkboxes.

    Shows:
    - Table: tab name, connection status, opt-in checkbox
    - Target count display
    - Emergency Stop button
    """

    broadcast_requested = Signal(bool)  # True=enabled, False=disabled

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tabs: dict[str, SshTerminalTab] = {}  # key -> tab
        self._row_keys: list[str] = []              # ordered row keys
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Title
        title = QLabel(_("📢 MultiExec"))
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px;")
        layout.addWidget(title)

        # Table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels([
            _("Session"), _("Status"), _("Opt-In"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 60)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { font-size: 12px; } "
            "QTableWidget::item { padding: 2px 4px; }"
        )
        layout.addWidget(self._table)

        # Target count
        self._target_label = QLabel(_("0 targets selected"))
        self._target_label.setStyleSheet("font-size: 12px; padding: 2px 4px;")
        layout.addWidget(self._target_label)

        # Emergency stop
        stop_row = QHBoxLayout()
        self._stop_btn = QPushButton(_("🛑 Emergency Stop"))
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #8b0000; color: white; "
            "font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #cc0000; }"
        )
        self._stop_btn.clicked.connect(self._emergency_stop)
        stop_row.addWidget(self._stop_btn)
        stop_row.addStretch()
        layout.addLayout(stop_row)

        self.setMinimumWidth(300)

    # ── public API ──────────────────────────────────────────────────────────

    def refresh_tabs(self, tabs: List[SshTerminalTab]) -> None:
        """Rebuild the table from a flat list of SSH tabs across all panes."""
        self._tabs.clear()
        for tab in tabs:
            key = id(tab)
            self._tabs[str(key)] = tab

        self._rebuild_table()

    def selected_count(self) -> int:
        """Number of tabs with opt-in checked."""
        count = 0
        for key in self._row_keys:
            tab = self._tabs.get(key)
            if tab and tab.broadcast_opted_in:
                count += 1
        return count

    def selected_tabs(self) -> List[SshTerminalTab]:
        """Return tabs that are both connected and opted-in."""
        result: list[SshTerminalTab] = []
        for key in self._row_keys:
            tab = self._tabs.get(key)
            if tab and tab.has_opt_in():
                result.append(tab)
        return result

    def clear_all(self) -> None:
        """Clear all opt-ins (e.g., on emergency stop)."""
        for tab in self._tabs.values():
            tab.broadcast_opted_in = False
        self._update_ui()

    # ── internal ────────────────────────────────────────────────────────────

    def _rebuild_table(self) -> None:
        """Rebuild table rows from current tabs."""
        keys = list(self._tabs.keys())
        if keys == self._row_keys:
            # Same set — just update
            self._update_ui()
            return

        self._row_keys = keys
        self._table.setRowCount(len(keys))

        for row, key in enumerate(keys):
            tab = self._tabs[key]

            # Session name
            name_item = QTableWidgetItem(tab.profile.name)
            name_item.setData(Qt.UserRole, key)
            self._table.setItem(row, 0, name_item)

            # Status
            status_text = (
                _("Connected") if tab._connected else _("Disconnected")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, status_item)

            # Opt-in checkbox
            cb = QCheckBox()
            cb.setChecked(tab.broadcast_opted_in)
            cb.setEnabled(tab._connected)
            cb.toggled.connect(lambda checked, k=key: self._on_opt_in_toggled(k, checked))
            self._table.setCellWidget(row, 2, cb)

        self._update_ui()

    def _update_ui(self) -> None:
        """Update status texts and target count."""
        count = self.selected_count()
        self._target_label.setText(
            _("{} target(s) selected").format(count)
        )

        # Update checkboxes and status text per row
        for row, key in enumerate(self._row_keys):
            tab = self._tabs.get(key)
            if tab is None:
                continue

            # Status
            status_item = self._table.item(row, 1)
            if status_item:
                status_item.setText(
                    _("Connected") if tab._connected else _("Disconnected")
                )

            # Checkbox
            cb = self._table.cellWidget(row, 2)
            if isinstance(cb, QCheckBox):
                cb.setEnabled(tab._connected)
                if not tab._connected and cb.isChecked():
                    cb.setChecked(False)

    def _on_opt_in_toggled(self, key: str, checked: bool) -> None:
        """Handle opt-in checkbox change."""
        tab = self._tabs.get(key)
        if tab:
            tab.broadcast_opted_in = checked
        self._update_ui()
        self._update_broadcast_state()

    def _emergency_stop(self) -> None:
        """Emergency stop: clear all opt-ins and disable broadcast."""
        self.clear_all()
        self.broadcast_requested.emit(False)

    def _update_broadcast_state(self) -> None:
        """Enable or disable broadcast based on selection count."""
        count = self.selected_count()
        if count > 0:
            self.broadcast_requested.emit(True)
        else:
            self.broadcast_requested.emit(False)
