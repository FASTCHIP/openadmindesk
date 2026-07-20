"""Tools Hub — built-in network utilities panel."""

from __future__ import annotations

import socket
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QDialog, QFormLayout,
    QLineEdit, QPlainTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import QThread, Signal


class _ToolRunner(QThread):
    """Run a tool function in a background thread."""
    output = Signal(str)
    finished = Signal()

    def __init__(self, target, args=None):
        super().__init__()
        self._target = target
        self._args = args or ()

    def run(self):
        try:
            result = self._target(*self._args)
            self.output.emit(result)
        except Exception as e:
            self.output.emit(f"Error: {e}")
        finally:
            self.finished.emit()


class _ToolDialog(QDialog):
    """Base dialog for built-in tools with input/output."""

    def __init__(self, title: str, input_label: str,
                 tool_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(500, 350)
        self._tool_fn = tool_fn
        self._runner: Optional[_ToolRunner] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText(input_label)
        form.addRow("Target:", self._input)
        layout.addLayout(form)

        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._run)
        layout.addWidget(self._run_btn)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            "font-family: monospace; font-size: 12px; "
            "background: #1e1e1e; color: #cccccc;"
        )
        layout.addWidget(self._output, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def _run(self):
        target = self._input.text().strip()
        if not target:
            return
        self._output.clear()
        self._run_btn.setEnabled(False)
        self._runner = _ToolRunner(self._tool_fn, (target,))
        self._runner.output.connect(self._output.appendPlainText)
        self._runner.finished.connect(lambda: self._run_btn.setEnabled(True))
        self._runner.start()

    def closeEvent(self, event):
        if self._runner and self._runner.isRunning():
            self._runner.quit()
            self._runner.wait(1000)
        super().closeEvent(event)


def _port_scan(target: str) -> str:
    """Scan common ports on a host."""
    host = target.strip()
    # Remove port if provided
    if ":" in host:
        host = host.split(":")[0]
    
    common_ports = [
        (21, "FTP"), (22, "SSH"), (23, "Telnet"),
        (25, "SMTP"), (53, "DNS"), (80, "HTTP"),
        (110, "POP3"), (143, "IMAP"), (443, "HTTPS"),
        (445, "SMB"), (993, "IMAPS"), (995, "POP3S"),
        (1433, "MSSQL"), (3306, "MySQL"), (3389, "RDP"),
        (5432, "PostgreSQL"), (5900, "VNC"), (6379, "Redis"),
        (8080, "HTTP-Alt"), (8443, "HTTPS-Alt"),
    ]
    lines = [f"Scanning {host} for common ports...\n"]
    open_count = 0
    for port, name in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                lines.append(f"  {port:5d}  OPEN  {name}")
                open_count += 1
        except Exception:
            lines.append(f"  {port:5d}  ERROR  {name}")
    lines.append(f"\n{open_count} open ports found.")
    return "\n".join(lines)


def _dns_lookup(target: str) -> str:
    """Resolve hostname to IP addresses."""
    host = target.strip()
    lines = [f"DNS lookup for {host}:\n"]
    try:
        info = socket.getaddrinfo(host, None)
        seen = set()
        for addr in info:
            ip = addr[4][0]
            if ip not in seen:
                seen.add(ip)
                family = "IPv6" if addr[0] == socket.AF_INET6 else "IPv4"
                lines.append(f"  {family}: {ip}")
    except socket.gaierror as e:
        lines.append(f"  Resolution failed: {e}")
    return "\n".join(lines)


def _http_check(target: str) -> str:
    """Check if an HTTP/HTTPS server responds."""
    url = target.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    lines = [f"HTTP check: {url}\n"]
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            lines.append(f"  Status: {resp.status} {resp.reason}")
            lines.append(f"  Server: {resp.headers.get('Server', 'unknown')}")
            content_type = resp.headers.get("Content-Type", "unknown")
            lines.append(f"  Type:   {content_type}")
            # Show first 200 chars of body
            body = resp.read(200).decode("utf-8", errors="replace")
            lines.append(f"\nFirst bytes:\n{body}")
    except urllib.error.HTTPError as e:
        lines.append(f"  HTTP Error: {e.code} {e.reason}")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return "\n".join(lines)


_TOOLS = [
    ("🔍  Port Scanner", "Scan common ports on a host",
     "hostname (e.g. example.com)", _port_scan),
    ("🌐  DNS Lookup", "Resolve hostname to IP addresses",
     "hostname (e.g. example.com)", _dns_lookup),
    ("🌍  HTTP Check", "Check HTTP/HTTPS server response",
     "URL or hostname (e.g. example.com)", _http_check),
]


class ToolsHub(QWidget):
    """Panel with built-in network utilities."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("🛠  Tools Hub")
        header.setStyleSheet("font-size: 15px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(4)

        note = QLabel(
            "Built-in Python utilities — no external tools required."
        )
        note.setStyleSheet("color: gray; font-size: 11px; padding: 4px;")
        note.setWordWrap(True)
        tools_layout.addWidget(note)
        tools_layout.addSpacing(8)

        for title, desc, placeholder, fn in _TOOLS:
            frame = QFrame()
            frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
            frame.setStyleSheet("QFrame { padding: 6px; }")

            row = QVBoxLayout(frame)
            
            btn = QPushButton(title)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left; padding: 8px; font-size: 13px;
                    border: 1px solid #ccc; border-radius: 4px;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            btn.setToolTip(desc)
            btn.clicked.connect(
                lambda checked=False, t=title, p=placeholder, f=fn:
                    self._open_tool(t, p, f)
            )
            row.addWidget(btn)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #666; font-size: 11px; padding-left: 4px;")
            row.addWidget(desc_label)

            tools_layout.addWidget(frame)

        tools_layout.addStretch()
        scroll.setWidget(tools_widget)
        layout.addWidget(scroll)

    def _open_tool(self, title: str, placeholder: str, tool_fn):
        dialog = _ToolDialog(title, placeholder, tool_fn, self)
        dialog.exec()

    def refresh_discovery(self) -> None:
        """No-op: tools are always available."""
        pass
