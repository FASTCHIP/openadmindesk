"""Tools Hub — local tool discovery and quick-launch panel."""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QScrollArea, QMessageBox, QFrame,
)
from PySide6.QtCore import Signal

from openadmindesk.core.l10n import _

# Tool definitions: (command, display_name, category, icon_emoji)
_TOOLS_TO_DISCOVER = [
    # Network
    ("nmap", "Nmap", "Network", "🔍"),
    ("tcpdump", "tcpdump", "Network", "📡"),
    ("iperf", "iperf3", "Network", "📊"),
    ("dig", "dig", "Network", "🌐"),
    ("nc", "netcat", "Network", "🔌"),
    ("traceroute", "traceroute", "Network", "🗺"),
    ("ping", "ping", "Network", "📶"),
    ("curl", "curl", "Network", "⬇"),
    ("wget", "wget", "Network", "⬇"),
    # Remote
    ("ssh", "OpenSSH", "Remote", "🖥"),
    ("sftp", "SFTP", "Remote", "📁"),
    ("rsync", "rsync", "Remote", "🔄"),
    ("xfreerdp", "FreeRDP", "Remote", "🪟"),
    ("vncviewer", "VNC Viewer", "Remote", "🖵"),
    # System
    ("htop", "htop", "System", "📈"),
    ("df", "df", "System", "💾"),
    ("du", "du", "System", "📁"),
    ("lsof", "lsof", "System", "🔓"),
    ("ps", "ps", "System", "📋"),
]


class ToolsHub(QWidget):
    """Panel that discovers installed tools and provides quick-launch."""

    launch_requested = Signal(str)  # emits command to launch

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._found: dict[str, str] = {}  # name → path
        self._discover()
        self._setup_ui()

    def _discover(self) -> None:
        """Scan for installed tools."""
        for cmd, name, __, __ in _TOOLS_TO_DISCOVER:
            path = shutil.which(cmd)
            if path:
                self._found[name] = path

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        found_count = len(self._found)
        total = len(_TOOLS_TO_DISCOVER)
        header = QLabel(_(f"🛠  Tools Hub  ({found_count}/{total} found)"))
        header.setStyleSheet("font-size: 15px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Scroll area with tool buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(4)

        categories: dict[str, list] = {}
        for cmd, name, category, icon in _TOOLS_TO_DISCOVER:
            if name not in self._found:
                continue
            categories.setdefault(category, []).append((name, icon, self._found[name]))

        for cat in ["Network", "Remote", "System"]:
            items = categories.get(cat, [])
            if not items:
                continue
            
            cat_label = QLabel(cat)
            cat_label.setStyleSheet("font-weight: bold; color: #007acc; padding: 4px 0;")
            tools_layout.addWidget(cat_label)

            for name, icon, path in items:
                row = QHBoxLayout()
                
                btn = QPushButton(f"{icon}  {name}")
                btn.setToolTip(f"Path: {path}\nClick to see launch options")
                btn.setFlat(True)
                btn.setStyleSheet("""
                    QPushButton { text-align: left; padding: 6px; border: none; border-radius: 3px; }
                    QPushButton:hover { background-color: #e0e0e0; }
                """)
                btn.clicked.connect(lambda checked, n=name, p=path: self._on_tool_click(n, p))
                row.addWidget(btn)
                row.addStretch()
                tools_layout.addLayout(row)

        tools_layout.addStretch()
        scroll.setWidget(tools_widget)
        layout.addWidget(scroll)

        # Info
        note = QLabel(_("Click a tool for launch options. More tools are auto-discovered on startup."))
        note.setStyleSheet("color: gray; font-size: 11px; padding: 4px;")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _on_tool_click(self, name: str, path: str) -> None:
        """Show launch options for a discovered tool."""
        reply = QMessageBox.question(
            self,
            _(f"Launch {name}"),
            _(f"Tool: {name}\nPath: {path}\n\nOpen in a new terminal window?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                subprocess.Popen(
                    ["x-terminal-emulator", "-e", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                # Fallback: try common terminals
                for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                    term_path = shutil.which(term)
                    if term_path:
                        try:
                            subprocess.Popen(
                                [term_path, "-e", path],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            break
                        except Exception:
                            continue
                else:
                    self.launch_requested.emit(path)

    def refresh_discovery(self) -> None:
        """Re-scan for tools and update UI."""
        self._found.clear()
        self._discover()
        # Remove old layout and rebuild
        self._setup_ui()
