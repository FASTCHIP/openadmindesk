"""Tunnel manager and X11 GUI launcher UI."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QToolBar,
    QToolButton,
    QLabel,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict

from openadmindesk.core.tunnel_profile import TunnelProfile, TunnelType
from openadmindesk.core.tunnel_manager import TunnelManager
from openadmindesk.core.x11_detector import X11Detector
from openadmindesk.core.gui_launcher import GuiLauncher


class TunnelDialog(QDialog):
    """Dialog for creating/editing a tunnel profile."""

    def __init__(self, profile: Optional[TunnelProfile] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.profile = profile or TunnelProfile()
        self.setWindowTitle("Edit Tunnel" if profile else "New Tunnel")
        self.setMinimumWidth(450)
        self.setModal(True)
        self._setup_ui()
        self._load_profile()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Tunnel")
        form.addRow("Name:", self.name_input)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("gateway.example.com")
        form.addRow("SSH Host:", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        form.addRow("SSH Port:", self.port_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("root")
        form.addRow("Username:", self.username_input)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("/path/to/key (optional)")
        form.addRow("Private Key:", self.key_input)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Local Forward (-L)", TunnelType.LOCAL_FORWARD.value)
        self.type_combo.addItem("Remote Forward (-R)", TunnelType.REMOTE_FORWARD.value)
        self.type_combo.addItem("Dynamic SOCKS (-D)", TunnelType.DYNAMIC_SOCKS.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Tunnel Type:", self.type_combo)

        # Local port (used by Local Forward and Remote Forward)
        self.local_port_input = QSpinBox()
        self.local_port_input.setRange(1024, 65535)
        self.local_port_input.setValue(8080)
        self.local_port_label = form.addRow("Local Port:", self.local_port_input)

        # Remote host (used by Local Forward)
        self.remote_host_input = QLineEdit()
        self.remote_host_input.setPlaceholderText("localhost")
        self.remote_host_input.setText("localhost")
        self.remote_host_label = form.addRow("Remote Host:", self.remote_host_input)

        # Remote port (used by Local Forward)
        self.remote_port_input = QSpinBox()
        self.remote_port_input.setRange(1, 65535)
        self.remote_port_input.setValue(80)
        self.remote_port_label = form.addRow("Remote Port:", self.remote_port_input)

        # SOCKS port (used by Dynamic SOCKS)
        self.socks_port_input = QSpinBox()
        self.socks_port_input.setRange(1024, 65535)
        self.socks_port_input.setValue(1080)
        self.socks_port_label = form.addRow("SOCKS Port:", self.socks_port_input)

        # Compression
        self.compression_check = QCheckBox("Enable Compression")
        form.addRow("", self.compression_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed(0)

    def _on_type_changed(self, index: int) -> None:
        """Show/hide fields based on tunnel type."""
        tunnel_type = self.type_combo.itemData(index)

        if tunnel_type == TunnelType.LOCAL_FORWARD.value:
            self.local_port_label.setVisible(True)
            self.local_port_input.setVisible(True)
            self.remote_host_label.setVisible(True)
            self.remote_host_input.setVisible(True)
            self.remote_port_label.setVisible(True)
            self.remote_port_input.setVisible(True)
            self.socks_port_label.setVisible(False)
            self.socks_port_input.setVisible(False)
        elif tunnel_type == TunnelType.REMOTE_FORWARD.value:
            self.local_port_label.setVisible(True)
            self.local_port_input.setVisible(True)
            self.remote_host_label.setVisible(True)
            self.remote_host_input.setVisible(True)
            self.remote_port_label.setVisible(True)
            self.remote_port_input.setVisible(True)
            self.socks_port_label.setVisible(False)
            self.socks_port_input.setVisible(False)
        elif tunnel_type == TunnelType.DYNAMIC_SOCKS.value:
            self.local_port_label.setVisible(False)
            self.local_port_input.setVisible(False)
            self.remote_host_label.setVisible(False)
            self.remote_host_input.setVisible(False)
            self.remote_port_label.setVisible(False)
            self.remote_port_input.setVisible(False)
            self.socks_port_label.setVisible(True)
            self.socks_port_input.setVisible(True)

    def _load_profile(self) -> None:
        """Load existing profile into form."""
        p = self.profile
        self.name_input.setText(p.name)
        self.host_input.setText(p.host)
        self.port_input.setValue(p.port)
        self.username_input.setText(p.username)
        self.key_input.setText(p.private_key_path or "")
        self.local_port_input.setValue(p.local_port or 8080)
        self.remote_host_input.setText(p.remote_host or "localhost")
        self.remote_port_input.setValue(p.remote_port or 80)
        self.socks_port_input.setValue(p.socks_port or 1080)
        self.compression_check.setChecked(p.compression)

        # Set tunnel type
        idx = self.type_combo.findData(p.tunnel_type.value)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

    def _validate_and_accept(self) -> None:
        """Validate and accept."""
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not self.host_input.text().strip():
            QMessageBox.warning(self, "Validation", "SSH Host is required.")
            return
        self.accept()

    def get_tunnel_profile(self) -> TunnelProfile:
        """Build TunnelProfile from form data."""
        p = self.profile
        p.name = self.name_input.text().strip()
        p.host = self.host_input.text().strip()
        p.port = self.port_input.value()
        p.username = self.username_input.text().strip()
        p.private_key_path = self.key_input.text().strip() or None
        p.compression = self.compression_check.isChecked()

        tunnel_type_str = self.type_combo.currentData()
        if tunnel_type_str == TunnelType.LOCAL_FORWARD.value:
            p.tunnel_type = TunnelType.LOCAL_FORWARD
            p.local_port = self.local_port_input.value()
            p.remote_host = self.remote_host_input.text().strip() or "localhost"
            p.remote_port = self.remote_port_input.value()
        elif tunnel_type_str == TunnelType.REMOTE_FORWARD.value:
            p.tunnel_type = TunnelType.REMOTE_FORWARD
            p.local_port = self.local_port_input.value()
            p.remote_host = self.remote_host_input.text().strip() or "localhost"
            p.remote_port = self.remote_port_input.value()
        elif tunnel_type_str == TunnelType.DYNAMIC_SOCKS.value:
            p.tunnel_type = TunnelType.DYNAMIC_SOCKS
            p.socks_port = self.socks_port_input.value()

        return p


class TunnelManagerWidget(QWidget):
    """Widget for managing SSH tunnels and launching X11 apps."""

    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.tunnel_manager = TunnelManager()
        self.x11_detector = X11Detector()
        self.gui_launcher = GuiLauncher()
        self._tunnel_profiles: Dict[str, TunnelProfile] = {}
        self._setup_ui()
        # Store connect/disconnect handler for later use
        self._status_handler = None

    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        add_btn = QToolButton()
        add_btn.setText("+ New Tunnel")
        add_btn.clicked.connect(self._add_tunnel)
        toolbar.addWidget(add_btn)

        stop_btn = QToolButton()
        stop_btn.setText("■ Stop")
        stop_btn.clicked.connect(self._stop_selected_tunnel)
        toolbar.addWidget(stop_btn)

        restart_btn = QToolButton()
        restart_btn.setText("↻ Restart")
        restart_btn.clicked.connect(self._restart_selected_tunnel)
        toolbar.addWidget(restart_btn)

        log_btn = QToolButton()
        log_btn.setText("📋 Log")
        log_btn.clicked.connect(self._view_tunnel_log)
        toolbar.addWidget(log_btn)

        toolbar.addSeparator()

        # X11 status
        x11_available = X11Detector.is_x11_available()
        self.x11_label = QLabel(
            "🖥 X11: Available" if x11_available else "🖥 X11: Not available"
        )
        self.x11_label.setStyleSheet(
            "color: green; font-weight: bold;" if x11_available else "color: gray;"
        )
        toolbar.addWidget(self.x11_label)

        launch_btn = QToolButton()
        launch_btn.setText("▶ Launch GUI App...")
        launch_btn.clicked.connect(self._launch_gui_app)
        launch_btn.setEnabled(x11_available)
        toolbar.addWidget(launch_btn)

        layout.addWidget(toolbar)

        # Info label
        self.info_label = QLabel(
            "Create a tunnel to forward ports or launch remote GUI applications."
        )
        self.info_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(self.info_label)

        # Tunnel list
        self.tunnel_tree = QTreeWidget()
        self.tunnel_tree.setHeaderLabels(["Name", "Type", "Target", "Status", "Uptime"])
        self.tunnel_tree.setColumnWidth(0, 150)
        self.tunnel_tree.setColumnWidth(1, 100)
        self.tunnel_tree.setColumnWidth(2, 180)
        self.tunnel_tree.setColumnWidth(3, 100)
        self.tunnel_tree.setColumnWidth(4, 80)
        self.tunnel_tree.setAlternatingRowColors(True)
        layout.addWidget(self.tunnel_tree)

        self.setMinimumSize(550, 300)

        # Periodic status refresh
        self._start_refresh_timer()

    def _start_refresh_timer(self) -> None:
        """Start timer to periodically refresh tunnel status."""
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_tunnel_status)
        self._timer.start(2000)  # every 2 seconds

    def _refresh_tunnel_status(self) -> None:
        """Update tunnel status indicators with live data."""
        for i in range(self.tunnel_tree.topLevelItemCount()):
            item = self.tunnel_tree.topLevelItem(i)
            tunnel_id = item.data(0, Qt.UserRole)
            if tunnel_id:
                running = self.tunnel_manager.is_tunnel_running(tunnel_id)
                if running:
                    item.setText(3, "● Running")
                    item.setForeground(3, Qt.green)
                    duration = self.tunnel_manager.get_tunnel_duration(tunnel_id)
                    if duration > 0:
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        item.setText(4, f"{mins}m {secs}s")
                else:
                    item.setText(3, "○ Stopped")
                    item.setForeground(3, Qt.gray)
                    item.setText(4, "—")

    def _add_tunnel(self) -> None:
        """Open dialog to create a new tunnel."""
        dialog = TunnelDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            profile = dialog.get_tunnel_profile()

            if not profile.is_valid():
                QMessageBox.warning(self, "Validation",
                    "Tunnel configuration is invalid. Check required fields.")
                return

            # Store profile
            self._tunnel_profiles[profile.id] = profile

            # Build display info
            if profile.tunnel_type == TunnelType.LOCAL_FORWARD:
                target = f"L{profile.local_port} → {profile.remote_host}:{profile.remote_port}"
            elif profile.tunnel_type == TunnelType.REMOTE_FORWARD:
                target = f"R{profile.remote_port} → localhost:{profile.local_port}"
            else:
                target = f"SOCKS {profile.socks_port}"

            # Add to tree
            item = QTreeWidgetItem([
                profile.name,
                profile.tunnel_type.value.replace("_", " ").title(),
                target,
                "○ Stopped",
                "—"
            ])
            item.setData(0, Qt.UserRole, profile.id)
            item.setForeground(3, Qt.red)
            self.tunnel_tree.addTopLevelItem(item)

            # Auto-start the tunnel
            self._start_tunnel(profile)

    def _start_tunnel(self, profile: TunnelProfile) -> None:
        """Start a tunnel."""
        success = self.tunnel_manager.start_tunnel(profile)
        if success:
            self.status_message.emit(f"Tunnel '{profile.name}' started")
        else:
            QMessageBox.critical(self, "Error",
                f"Failed to start tunnel '{profile.name}'.\n"
                "Check SSH host credentials.")

    def _stop_selected_tunnel(self) -> None:
        """Stop the selected tunnel."""
        item = self.tunnel_tree.currentItem()
        if not item:
            return

        tunnel_id = item.data(0, Qt.UserRole)
        if tunnel_id and self.tunnel_manager.stop_tunnel(tunnel_id):
            item.setText(3, "○ Stopped")
            item.setForeground(3, Qt.red)
            self.status_message.emit(f"Tunnel '{item.text(0)}' stopped")

    def _restart_selected_tunnel(self) -> None:
        """Restart the selected tunnel."""
        item = self.tunnel_tree.currentItem()
        if not item:
            return
        tunnel_id = item.data(0, Qt.UserRole)
        if tunnel_id:
            self.tunnel_manager.restart_tunnel(tunnel_id)
            self.status_message.emit("Tunnel restarted")

    def _view_tunnel_log(self) -> None:
        """Show stderr log for selected tunnel."""
        item = self.tunnel_tree.currentItem()
        if not item:
            return
        tunnel_id = item.data(0, Qt.UserRole)
        if tunnel_id:
            log_text = self.tunnel_manager.get_tunnel_stderr(tunnel_id)
            if log_text:
                QMessageBox.information(self, "Tunnel Log", log_text[:5000])
            else:
                QMessageBox.information(self, "Tunnel Log", "No log output available.")

    def _launch_gui_app(self) -> None:
        """Dialog to launch a remote GUI app with X11 forwarding."""
        if not X11Detector.is_x11_available():
            QMessageBox.warning(self, "X11 Not Available",
                "X11 forwarding is not available on this system.\n"
                "Make sure DISPLAY is set and X11/Xwayland is running.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Launch Remote GUI Application")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        host_input = QLineEdit()
        host_input.setPlaceholderText("remote-server.example.com")
        form.addRow("Host:", host_input)

        port_input = QSpinBox()
        port_input.setRange(1, 65535)
        port_input.setValue(22)
        form.addRow("Port:", port_input)

        username_input = QLineEdit()
        username_input.setPlaceholderText("root")
        form.addRow("Username:", username_input)

        command_input = QLineEdit()
        command_input.setPlaceholderText("xclock")
        command_input.setText("xclock")
        form.addRow("Command:", command_input)

        layout.addLayout(form)

        info_label = QLabel(
            "The command will be launched on the remote host with X11 forwarding.\n"
            "Examples: xclock, xeyes, firefox, gedit"
        )
        info_label.setStyleSheet("color: gray;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            host = host_input.text().strip()
            command = command_input.text().strip()

            if not host or not command:
                QMessageBox.warning(dialog, "Validation",
                    "Host and command are required.")
                return

            # Build a temporary tunnel profile for the SSH connection
            profile = TunnelProfile(
                name=f"x11-{host}",
                host=host,
                port=port_input.value(),
                username=username_input.text().strip()
            )

            display = X11Detector.get_x11_display()
            success = self.gui_launcher.launch_gui_app(profile, command)
            if success:
                self.status_message.emit(
                    f"Launched '{command}' on {host} (DISPLAY={display})"
                )
            else:
                QMessageBox.critical(dialog, "Launch Failed",
                    f"Failed to launch '{command}' on {host}.")

    def closeEvent(self, event) -> None:
        """Stop all tunnels on close."""
        # Stop all active tunnels
        for tunnel_id in list(self._tunnel_profiles.keys()):
            self.tunnel_manager.stop_tunnel(tunnel_id)
        event.accept()
