"""Remote system monitor — CPU, RAM, Disk for an SSH session."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import QTimer, Signal

from openadmindesk.core.ssh_terminal_backend import SSHTerminalBackend
from openadmindesk.core.l10n import _


class RemoteMonitor(QWidget):
    """Shows CPU, RAM, Disk stats for a remote server."""

    status_message = Signal(str)

    def __init__(self, backend: SSHTerminalBackend, parent=None) -> None:
        super().__init__(parent)
        self.backend = backend
        self._buffer = ""
        self._expecting = ""  # which command are we waiting for

        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # every 5 seconds
        self._refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel(_("📊 Remote Monitor"))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #cccccc;")
        layout.addWidget(header)

        self.info = QLabel("")
        self.info.setStyleSheet("color: #969696; font-size: 12px;")
        layout.addWidget(self.info)

        # Stats table
        self.table = QTableWidget(3, 2)
        self.table.setHorizontalHeaderLabels([_("Metric"), _("Value")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(120)
        layout.addWidget(self.table)

        # Refresh button
        btn_layout = QHBoxLayout()
        refresh = QPushButton(_("🔄 Refresh"))
        refresh.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh)
        auto_label = QLabel(_("Auto-refresh: 5s"))
        auto_label.setStyleSheet("color: #969696;")
        btn_layout.addWidget(auto_label)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _refresh(self) -> None:
        """Send monitoring commands to the remote host."""
        if not self.backend.is_connected():
            self.info.setText(_("Not connected"))
            return

        self._buffer = ""
        self._expecting = "cpu"
        # Use a one-liner that gives CPU, RAM, Disk, Uptime
        cmd = (
            "echo '---CPU---'; top -bn1 | head -3; "
            "echo '---RAM---'; free -h | grep -E '^Mem:|^Swap:'; "
            "echo '---DISK---'; df -h / | tail -1; "
            "echo '---UP---'; uptime; "
            "echo '---END---'\r"
        )
        self.backend.send(cmd)

    def feed(self, data: str) -> None:
        """Receive output from the remote host."""
        self._buffer += data
        if "---END---" not in self._buffer:
            return
        self._parse(self._buffer)

    def _parse(self, output: str) -> None:
        """Parse the collected output and update the table."""
        lines = output.split("\n")

        cpu = ""
        ram = ""
        disk = ""
        uptime = ""
        section = ""

        for line in lines:
            line = line.strip()
            if line.startswith("---CPU---"):
                section = "cpu"
                continue
            elif line.startswith("---RAM---"):
                section = "ram"
                continue
            elif line.startswith("---DISK---"):
                section = "disk"
                continue
            elif line.startswith("---UP---"):
                section = "up"
                continue
            elif line.startswith("---END---"):
                break

            if section == "cpu" and line and not line.startswith("top"):
                cpu += line + " | "
            elif section == "ram" and line:
                parts = line.split()
                if len(parts) >= 2:
                    ram += f"{parts[0]}: {parts[1]} used, {parts[-1]} free | "
            elif section == "disk" and line:
                parts = line.split()
                if len(parts) >= 5:
                    disk = f"{parts[-1]} used of {parts[1]} ({parts[4]})"
            elif section == "up" and line:
                uptime = line.replace("load average:", "Load:")

        self.table.setItem(0, 0, QTableWidgetItem(_("CPU")))
        self.table.setItem(0, 1, QTableWidgetItem(cpu.rstrip(" |")))
        self.table.setItem(1, 0, QTableWidgetItem(_("RAM")))
        self.table.setItem(1, 1, QTableWidgetItem(ram.rstrip(" |")))
        self.table.setItem(2, 0, QTableWidgetItem(_("Disk")))
        self.table.setItem(2, 1, QTableWidgetItem(disk))
        self.info.setText(uptime)
