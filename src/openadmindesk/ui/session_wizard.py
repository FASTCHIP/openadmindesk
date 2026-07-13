"""Session creation wizard -- guided setup for new connections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from openadmindesk.core.account import Account
from openadmindesk.core.l10n import _
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.vault_manager import VaultManager


@dataclass(frozen=True)
class _ProtocolOption:
    key: str
    label: str
    icon: str
    description: str
    session_type: Optional[SessionType]
    enabled: bool = True
    note: str = ""


@dataclass(frozen=True)
class _ProfileTemplate:
    key: str
    label: str
    name: str
    host: str
    username: str
    port: int


_PROTOCOL_OPTIONS = (
    _ProtocolOption(
        "ssh", "SSH", "SSH", "Secure shell terminal", SessionType.SSH
    ),
    _ProtocolOption(
        "rdp", "RDP", "RDP", "Windows remote desktop", SessionType.RDP
    ),
    _ProtocolOption(
        "telnet", "Telnet", "TEL", "Plain TCP terminal", SessionType.TELNET
    ),
    _ProtocolOption(
        "vnc", "VNC", "VNC", "Remote framebuffer desktop", SessionType.VNC
    ),
    _ProtocolOption(
        "local", "Local Shell", "LOC", "Shell on this workstation",
        SessionType.LOCAL_SHELL,
    ),
    _ProtocolOption(
        "sftp", "SFTP", "SFTP", "File browser over SSH", None, False,
        "Use an SSH profile for now; dedicated SFTP profiles are planned.",
    ),
    _ProtocolOption(
        "ftp", "FTP", "FTP", "Legacy file transfer", None, False,
        "Planned placeholder.",
    ),
    _ProtocolOption(
        "serial", "Serial", "SER", "Console over serial port", None, False,
        "Planned placeholder.",
    ),
    _ProtocolOption(
        "browser", "Browser", "WEB", "Open a web endpoint", None, False,
        "Planned placeholder.",
    ),
    _ProtocolOption(
        "mosh", "Mosh", "MOSH", "Roaming shell session", None, False,
        "Planned placeholder.",
    ),
)

_PROTO_LABELS = {
    option.session_type: option.label
    for option in _PROTOCOL_OPTIONS
    if option.session_type is not None
}
_PROTO_PORTS = {
    SessionType.SSH: 22,
    SessionType.RDP: 3389,
    SessionType.TELNET: 23,
    SessionType.LOCAL_SHELL: 1,
    SessionType.VNC: 5900,
}
_TEMPLATES = {
    SessionType.SSH: (
        _ProfileTemplate("linux_ssh", "Linux SSH", "Linux SSH", "server.example.com", "root", 22),
        _ProfileTemplate("jump_ssh", "Jump-host SSH", "Jump Host", "jump.example.com", "admin", 22),
    ),
    SessionType.RDP: (
        _ProfileTemplate("windows_rdp", "Windows RDP", "Windows Desktop", "windows.example.com", "Administrator", 3389),
    ),
    SessionType.TELNET: (
        _ProfileTemplate("network_telnet", "Network Telnet", "Network Device", "switch.example.com", "admin", 23),
    ),
    SessionType.VNC: (
        _ProfileTemplate("vnc", "VNC", "VNC Desktop", "desktop.example.com", "", 5900),
    ),
    SessionType.LOCAL_SHELL: (
        _ProfileTemplate("local_shell", "Local shell", "Local Shell", "localhost", "", 1),
    ),
}
_LAUNCH_SAVE_ONLY = "save_only"
_LAUNCH_SAVE_CONNECT = "save_connect"
_LAUNCH_TEMP_CONNECT = "temporary_connect"


class SessionWizard(QWizard):
    """Guided wizard for creating new session profiles."""

    def __init__(
        self,
        store: ProfileStore,
        vault: Optional[VaultManager] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.vault = vault
        self.setWindowTitle(_("New Session"))
        self.setMinimumSize(680, 520)
        self.setWizardStyle(QWizard.ModernStyle)

        self.protocol_page = _ProtocolPage(self)
        self.connection_page = _ConnectionPage(self)
        self.credential_page = _CredentialPage(self)
        self.ssh_advanced_page = _SshAdvancedPage(self)
        self.rdp_advanced_page = _RdpAdvancedPage(self)
        self.vnc_advanced_page = _VncAdvancedPage(self)
        self.summary_page = _SummaryPage(self)

        self.addPage(self.protocol_page)      # 0
        self.addPage(self.connection_page)     # 1
        self.addPage(self.credential_page)     # 2
        self.addPage(self.ssh_advanced_page)   # 3
        self.addPage(self.rdp_advanced_page)   # 4
        self.addPage(self.vnc_advanced_page)   # 5
        self.addPage(self.summary_page)        # 6

    def nextId(self) -> int:
        """Route pages based on session type."""
        current = self.currentId()
        st = self.protocol_page.selected_type()

        if current == 0:  # ProtocolPage → ConnectionPage
            return 1
        if current == 1:  # ConnectionPage → CredentialPage
            return 2

        if current == 2:  # CredentialPage → Advanced or Summary
            if st == SessionType.SSH:
                return 3  # ssh advanced
            elif st == SessionType.RDP:
                return 4  # rdp advanced
            elif st == SessionType.VNC:
                return 5  # vnc advanced
            else:
                return 6  # skip to summary (telnet, local)

        if current == 3:  # SSH Advanced → Summary
            return 6
        if current == 4:  # RDP Advanced → Summary
            return 6
        if current == 5:  # VNC Advanced → Summary
            return 6

        return -1  # finish

    def accept(self) -> None:
        """Create the profile on finish."""
        profile = self._build_profile()
        if not profile:
            # Invalid profile, do not close
            return
            
        # Handle credential save modes
        launch_behavior = self.launch_behavior()
        if launch_behavior == _LAUNCH_TEMP_CONNECT:
            # Temporary connect mode - no vault/store calls, just set _saved_profile
            self._saved_profile = profile
            super().accept()
            return
            
        # For save modes, check vault state and handle accordingly
        credential_id = profile.credential_id
        password = profile.password
        
        # If password entered but vault is absent or locked, show error
        if password and (not self.vault or not self.vault.is_unlocked()):
            QMessageBox.critical(
                self,
                _("Vault Required"),
                _("A vault is required to save passwords. Please unlock the vault first.")
            )
            return
            
        # If vault is unlocked and password is entered, save to vault
        if password and self.vault and self.vault.is_unlocked():
            # Create account with entered password
            account = Account(
                name=str(profile.name),
                username=str(profile.username),
                password=str(password),
                host=str(profile.host or "localhost"),
                port=profile.port,
                service_type=profile.session_type.value,
            )
            # If credential_id exists, preserve it and other fields
            if credential_id:
                account.id = credential_id
            try:
                if self.vault.add_account(account):
                    # Successfully added to vault, update profile
                    profile = profile.replace(credential_id=account.id, password=None)
                else:
                    # Vault error - return without saving
                    QMessageBox.critical(
                        self,
                        _("Vault Error"),
                        _("Failed to save account to vault.")
                    )
                    return
            except Exception:
                # Vault error - return without saving
                QMessageBox.critical(
                    self,
                    _("Vault Error"),
                    _("Failed to save account to vault.")
                )
                return
                
        # If store.save_profile fails, return without saving
        try:
            if not self.store.save_profile(profile):
                QMessageBox.critical(
                    self,
                    _("Save Error"),
                    _("Failed to save profile.")
                )
                return
        except Exception:
            QMessageBox.critical(
                self,
                _("Save Error"),
                _("Failed to save profile.")
            )
            return
            
        # Success - set _saved_profile and close
        self._saved_profile = profile
        super().accept()

    def created_profile(self) -> Optional[Profile]:
        return getattr(self, "_saved_profile", None)

    def profile(self) -> Optional[Profile]:
        return getattr(self, "_saved_profile", None)

    def launch_behavior(self) -> str:
        return self.credential_page.launch_behavior()

    def connect_after(self) -> bool:
        return self.launch_behavior() in {
            _LAUNCH_SAVE_CONNECT,
            _LAUNCH_TEMP_CONNECT,
        }

    def _build_profile(self) -> Optional[Profile]:
        """Build profile without side effects."""
        st = self.protocol_page.selected_type()
        name = self.field("name")
        host = self.field("host")
        if not st or not name:
            return None
        if st != SessionType.LOCAL_SHELL and not host:
            return None
        port = int(self.field("port"))
        username = self.field("username") or ""
        password = self.field("password") or None
        private_key_path = self.field("private_key") or None
        credential_id = self.credential_page.selected_credential_id()
        
        # Return password in memory unless existing credential ID is selected with empty password
        # This makes _build_profile side-effect free
        if credential_id and not password:
            # Existing credential selected with no password - return None for password
            password = None
        elif not credential_id and password:
            # New credential with password - return password in memory
            pass
        elif credential_id and password:
            # Existing credential with new password - return password in memory
            pass
        else:
            # No credential ID and no password - return None for password
            password = None
            
        # Common fields
        kwargs: dict = dict(
            name=name,
            host=host or "localhost",
            port=port,
            username=username,
            session_type=st,
            password=password,
            private_key_path=private_key_path,
            private_key_passphrase=None,
            credential_id=credential_id,
            parent_folder=self.connection_page.selected_folder(),
        )

        # SSH advanced (read directly from widgets for unvisited pages)
        if st == SessionType.SSH:
            kwargs["use_ssh_agent"] = self.ssh_advanced_page.agent_cb.isChecked()
            kwargs["compression"] = self.ssh_advanced_page.compression_cb.isChecked()
            kwargs["keep_alive"] = self.ssh_advanced_page.keepalive_cb.isChecked()
            kwargs["x11_forwarding"] = self.ssh_advanced_page.x11_cb.isChecked()
            proxy = self.ssh_advanced_page.proxy_input.text().strip()
            kwargs["proxy_command"] = proxy or None

        # RDP advanced
        if st == SessionType.RDP:
            kwargs["rdp_gateway"] = self.rdp_advanced_page.gateway_input.text().strip() or None
            kwargs["rdp_gateway_username"] = self.rdp_advanced_page.gateway_user_input.text().strip() or None
            cert_idx = self.rdp_advanced_page.cert_combo.currentIndex()
            kwargs["rdp_certificate_policy"] = self.rdp_advanced_page.cert_combo.itemData(cert_idx) or "auto"
            kwargs["rdp_drive_redirection"] = self.rdp_advanced_page.drive_cb.isChecked()
            dp = self.rdp_advanced_page.drive_path_input.text().strip()
            kwargs["rdp_drive_path"] = dp or None
            kwargs["rdp_printer_redirection"] = self.rdp_advanced_page.printer_cb.isChecked()
            kwargs["rdp_clipboard_redirection"] = self.rdp_advanced_page.clipboard_cb.isChecked()
            kwargs["rdp_multimon"] = self.rdp_advanced_page.multimon_cb.isChecked()

        # VNC advanced
        if st == SessionType.VNC:
            kwargs["vnc_scaling"] = self.vnc_advanced_page.scaling_cb.isChecked()
            kwargs["vnc_view_only"] = self.vnc_advanced_page.viewonly_cb.isChecked()
            c_idx = self.vnc_advanced_page.color_combo.currentIndex()
            kwargs["vnc_color_depth"] = int(self.vnc_advanced_page.color_combo.itemData(c_idx) or 24)

        # Notes
        notes = self.summary_page.notes_input.text().strip()
        if notes:
            kwargs["notes"] = notes

        return Profile(**kwargs)


class _ProtocolPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("Choose Protocol"))
        self.setSubTitle(_("Select the connection type. Planned protocols are shown but disabled."))

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(8)
        layout.addLayout(grid)

        self._buttons: list[QPushButton] = []
        self._option_buttons: dict[str, QPushButton] = {}
        self._selected_type: Optional[SessionType] = None

        for index, option in enumerate(_PROTOCOL_OPTIONS):
            btn = self._make_button(option)
            row, column = divmod(index, 5)
            grid.addWidget(btn, row, column)
            self._buttons.append(btn)
            self._option_buttons[option.key] = btn

        self.planned_hint = QLabel(
            _("Disabled entries are visible roadmap items, not hidden features.")
        )
        self.planned_hint.setWordWrap(True)
        layout.addWidget(self.planned_hint)
        layout.addStretch(1)
        self.registerField("session_type", self, "selected_type")

    def _make_button(self, option: _ProtocolOption) -> QPushButton:
        suffix = "" if option.enabled else "\nPlanned"
        btn = QPushButton(
            f"{option.icon}\n{option.label}\n{option.description}{suffix}"
        )
        btn.setMinimumSize(112, 82)
        btn.setCheckable(option.enabled)
        btn.setEnabled(option.enabled)
        btn.setToolTip(option.note or option.description)
        if option.enabled and option.session_type is not None:
            btn.clicked.connect(lambda checked=False, st=option.session_type: self._select(st))
        return btn

    def _select(self, st: SessionType) -> None:
        self._selected_type = st
        for btn in self._buttons:
            btn.setChecked(False)
            btn.setStyleSheet("")
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setChecked(True)
            sender.setStyleSheet("border: 2px solid #007acc;")
        else:
            for option in _PROTOCOL_OPTIONS:
                if option.session_type == st:
                    btn = self._option_buttons[option.key]
                    btn.setChecked(True)
                    btn.setStyleSheet("border: 2px solid #007acc;")
                    break
        self.completeChanged.emit()

    def selected_type(self) -> Optional[SessionType]:
        return self._selected_type

    def set_selected_type(self, val: SessionType) -> None:
        if val in _PROTO_LABELS:
            self._select(val)

    def isComplete(self) -> bool:
        return self._selected_type is not None


class _ConnectionPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("Connection Details"))
        self.setSubTitle(_("Enter the host address and session name."))

        layout = QFormLayout(self)

        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(self._apply_template)
        layout.addRow(_("Template:"), self.template_combo)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Server")
        self.registerField("name*", self.name_input)
        layout.addRow(_("Name:"), self.name_input)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("server.example.com")
        self.registerField("host*", self.host_input)
        layout.addRow(_("Host:"), self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.registerField("port", self.port_input)
        layout.addRow(_("Port:"), self.port_input)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addRow(_("Summary:"), self.summary_label)

        self.folder_combo = QComboBox()
        self.folder_combo.addItem(f"📁 {_('(None)')}", "")
        try:
            if parent and hasattr(parent, "store"):
                for folder in parent.store.load_all_folders():
                    self.folder_combo.addItem(f"📁 {folder.name}", folder.name)
        except Exception:
            pass
        layout.addRow(_("Folder:"), self.folder_combo)

        self.name_input.textChanged.connect(self._update_summary)
        self.host_input.textChanged.connect(self._update_summary)
        self.port_input.valueChanged.connect(self._update_summary)

    def initializePage(self) -> None:
        wizard = self.wizard()
        st = wizard.protocol_page.selected_type() if wizard else None
        self._load_templates(st)
        self.port_input.setValue(_PROTO_PORTS.get(st, 22))
        local_shell = st == SessionType.LOCAL_SHELL
        self.host_input.setEnabled(not local_shell)
        self.port_input.setEnabled(not local_shell)
        if local_shell:
            self.host_input.setText("localhost")
        self._update_summary()

    def selected_folder(self) -> Optional[str]:
        value = self.folder_combo.currentData()
        return value or None

    def _load_templates(self, st: Optional[SessionType]) -> None:
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem(_("Custom"), None)
        for template in _TEMPLATES.get(st, ()):
            self.template_combo.addItem(template.label, template)
        self.template_combo.blockSignals(False)

    def _apply_template(self) -> None:
        template = self.template_combo.currentData()
        if not isinstance(template, _ProfileTemplate):
            return
        self.name_input.setText(template.name)
        self.host_input.setText(template.host)
        self.port_input.setValue(template.port)
        wizard = self.wizard()
        if wizard and not wizard.credential_page.username_input.text():
            wizard.credential_page.username_input.setText(template.username)
        self._update_summary()

    def _update_summary(self) -> None:
        wizard = self.wizard()
        st = wizard.protocol_page.selected_type() if wizard else None
        label = _PROTO_LABELS.get(st, "Session")
        name = self.name_input.text() or "<name>"
        host = self.host_input.text() or "<host>"
        port = self.port_input.value()
        if st == SessionType.LOCAL_SHELL:
            self.summary_label.setText(f"{label}: {name}")
        else:
            self.summary_label.setText(f"{label}: {name} -> {host}:{port}")


class _CredentialPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("Credentials And Launch"))
        self.setSubTitle(_("Choose credentials and what should happen after Finish."))

        layout = QFormLayout(self)

        self.vault_account_selector = QComboBox()
        self.vault_account_selector.addItem(_("(none -- create from password)"), "")
        self.vault_account_selector.currentIndexChanged.connect(
            self._on_vault_account_selected
        )
        if parent and getattr(parent, "vault", None) and parent.vault.is_unlocked():
            layout.addRow(_("Vault Account:"), self.vault_account_selector)
            self._load_vault_accounts(parent.vault)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("root")
        self.registerField("username", self.username_input)
        layout.addRow(_("Username:"), self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.registerField("password", self.password_input)
        layout.addRow(_("Password:"), self.password_input)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("/path/to/id_rsa (optional)")
        key_browse = QPushButton(_("Browse..."))
        key_browse.clicked.connect(self._browse_key)
        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(key_browse)
        self.registerField("private_key", self.key_input)
        layout.addRow(_("Private Key:"), key_row)

        self.launch_combo = QComboBox()
        self.launch_combo.addItem(_("Save only"), _LAUNCH_SAVE_ONLY)
        self.launch_combo.addItem(_("Save and connect"), _LAUNCH_SAVE_CONNECT)
        self.launch_combo.addItem(_("Temporary connect"), _LAUNCH_TEMP_CONNECT)
        layout.addRow(_("Finish action:"), self.launch_combo)

        self.connect_check = QCheckBox(_("Connect after saving"))
        self.connect_check.setVisible(False)
        self.registerField("connect_after", self.connect_check)

    def _load_vault_accounts(self, vault: VaultManager) -> None:
        for account in vault.get_all_accounts():
            label = f"{account.name} ({account.username}@{account.host})"
            self.vault_account_selector.addItem(label, account.id)

    def selected_credential_id(self) -> Optional[str]:
        return self.vault_account_selector.currentData() or None

    def launch_behavior(self) -> str:
        return self.launch_combo.currentData() or _LAUNCH_SAVE_ONLY

    def _on_vault_account_selected(self, index: int) -> None:
        wizard = self.wizard()
        vault = getattr(wizard, "vault", None)
        if not vault or not vault.is_unlocked():
            return
        account_id = self.vault_account_selector.itemData(index)
        if not account_id:
            return
        account = vault.get_account(account_id)
        if not account:
            return
        if account.username and not self.username_input.text():
            self.username_input.setText(account.username)
        self.password_input.clear()

    def _browse_key(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Select SSH Private Key"),
            "",
            _("SSH Keys (*.pem *.key *id_*);;All Files (*)"),
        )
        if path:
            self.key_input.setText(path)


class _SshAdvancedPage(QWizardPage):
    """Advanced SSH options: agent, proxy, compression, keepalive, X11."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("SSH Advanced Options"))
        self.setSubTitle(_("Configure agent forwarding, proxy/jump host, compression, and more."))

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.agent_cb = QCheckBox(_("Use SSH agent"))
        self.agent_cb.setToolTip(_("Forward SSH agent to remote host for key-based auth."))
        self.registerField("use_ssh_agent", self.agent_cb)
        form.addRow("", self.agent_cb)

        self.compression_cb = QCheckBox(_("Enable compression"))
        self.compression_cb.setToolTip(_("Compress SSH data (-C flag)."))
        self.registerField("compression", self.compression_cb)
        form.addRow("", self.compression_cb)

        self.keepalive_cb = QCheckBox(_("Enable keep-alive"))
        self.keepalive_cb.setChecked(True)
        self.keepalive_cb.setToolTip(_("Send keep-alive packets to maintain the connection."))
        self.registerField("keep_alive", self.keepalive_cb)
        form.addRow("", self.keepalive_cb)

        self.x11_cb = QCheckBox(_("Forward X11 display"))
        self.x11_cb.setToolTip(_("Enable X11 forwarding for remote GUI apps (-X flag)."))
        self.registerField("x11_forwarding", self.x11_cb)
        form.addRow("", self.x11_cb)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("ssh -W %h:%p jump.example.com")
        self.proxy_input.setToolTip(_("ProxyCommand for SSH (e.g. 'ssh -W %h:%p bastion.example.com')."))
        self.registerField("proxy_command", self.proxy_input)
        form.addRow(_("Proxy command:"), self.proxy_input)

        layout.addLayout(form)
        layout.addStretch(1)


class _RdpAdvancedPage(QWizardPage):
    """Advanced RDP options: gateway, certificates, drives, printers, multimon, clipboard."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("RDP Advanced Options"))
        self.setSubTitle(_("Configure gateway, redirection, and display settings."))

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Gateway
        self.gateway_input = QLineEdit()
        self.gateway_input.setPlaceholderText("gateway.example.com")
        self.registerField("rdp_gateway", self.gateway_input)
        form.addRow(_("Gateway:"), self.gateway_input)

        self.gateway_user_input = QLineEdit()
        self.gateway_user_input.setPlaceholderText("user")
        self.registerField("rdp_gateway_username", self.gateway_user_input)
        form.addRow(_("Gateway user:"), self.gateway_user_input)

        # Certificate policy
        self.cert_combo = QComboBox()
        self.cert_combo.addItem(_("Automatic"), "auto")
        self.cert_combo.addItem(_("Warn on mismatch"), "warn")
        self.cert_combo.addItem(_("Ignore"), "ignore")
        self.registerField("rdp_certificate_policy", self.cert_combo)
        form.addRow(_("Certificate policy:"), self.cert_combo)

        # Redirections
        self.drive_cb = QCheckBox(_("Redirect drives"))
        self.registerField("rdp_drive_redirection", self.drive_cb)
        form.addRow("", self.drive_cb)

        self.drive_path_input = QLineEdit()
        self.drive_path_input.setPlaceholderText("/path/to/share")
        self.drive_path_input.setEnabled(False)
        self.registerField("rdp_drive_path", self.drive_path_input)
        form.addRow(_("Drive path:"), self.drive_path_input)
        self.drive_cb.toggled.connect(self.drive_path_input.setEnabled)

        self.printer_cb = QCheckBox(_("Redirect printers"))
        self.registerField("rdp_printer_redirection", self.printer_cb)
        form.addRow("", self.printer_cb)

        self.clipboard_cb = QCheckBox(_("Clipboard redirection"))
        self.clipboard_cb.setChecked(True)
        self.registerField("rdp_clipboard_redirection", self.clipboard_cb)
        form.addRow("", self.clipboard_cb)

        self.multimon_cb = QCheckBox(_("Use all monitors"))
        self.registerField("rdp_multimon", self.multimon_cb)
        form.addRow("", self.multimon_cb)

        layout.addLayout(form)
        layout.addStretch(1)


class _VncAdvancedPage(QWizardPage):
    """Advanced VNC options: scaling, view-only, color depth."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("VNC Advanced Options"))
        self.setSubTitle(_("Configure scaling, view-only mode, and color depth."))

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.scaling_cb = QCheckBox(_("Enable scaling"))
        self.scaling_cb.setToolTip(_("Scale remote desktop to fit the local window."))
        self.registerField("vnc_scaling", self.scaling_cb)
        form.addRow("", self.scaling_cb)

        self.viewonly_cb = QCheckBox(_("View-only mode"))
        self.viewonly_cb.setToolTip(_("Do not send keyboard or mouse input to the remote host."))
        self.registerField("vnc_view_only", self.viewonly_cb)
        form.addRow("", self.viewonly_cb)

        self.color_combo = QComboBox()
        self.color_combo.addItem(_("8-bit (256 colors)"), 8)
        self.color_combo.addItem(_("16-bit (High color)"), 16)
        self.color_combo.addItem(_("24-bit (True color)"), 24)
        self.color_combo.addItem(_("32-bit (Deep color)"), 32)
        self.color_combo.setCurrentIndex(2)  # 24-bit default
        self.registerField("vnc_color_depth", self.color_combo)
        form.addRow(_("Color depth:"), self.color_combo)

        layout.addLayout(form)
        layout.addStretch(1)


class _SummaryPage(QWizardPage):
    """Final summary with security notes before Finish."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(_("Summary & Security Notes"))
        self.setSubTitle(_("Review your session configuration before finishing."))

        layout = QVBoxLayout(self)

        self.summary_text = QLabel("")
        self.summary_text.setWordWrap(True)
        self.summary_text.setStyleSheet(
            "QLabel { background: #1e1e1e; color: #cccccc; "
            "padding: 12px; border-radius: 4px; font-size: 12px; "
            "font-family: monospace; }"
        )
        layout.addWidget(self.summary_text)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText(_("Optional session notes"))
        self.registerField("notes", self.notes_input)
        layout.addWidget(QLabel(_("Notes:")))
        layout.addWidget(self.notes_input)

        security_note = QLabel(
            _("🔒 Security note: passwords and private key passphrases are stored "
              "in the encrypted vault when a master password is set, never in plaintext "
              "profile files.")
        )
        security_note.setWordWrap(True)
        security_note.setStyleSheet("color: #dcaa3a; font-size: 11px; padding: 6px;")
        layout.addWidget(security_note)
        layout.addStretch(1)

    def initializePage(self) -> None:
        """Build summary text from current wizard fields."""
        wizard = self.wizard()
        if not wizard:
            return

        st = wizard.protocol_page.selected_type()
        lines: list[str] = []

        # Basic info
        lines.append(f"Protocol:  {_PROTO_LABELS.get(st, '?')}")
        lines.append(f"Name:      {wizard.connection_page.name_input.text() or '<not set>'}")
        if st != SessionType.LOCAL_SHELL:
            lines.append(f"Host:      {wizard.connection_page.host_input.text() or '<not set>'}")
            lines.append(f"Port:      {wizard.connection_page.port_input.value()}")
            lines.append(f"Username:  {wizard.credential_page.username_input.text() or '(none)'}")

        lines.append(f"Folder:    {wizard.connection_page.selected_folder() or '(none)'}")

        # SSH advanced
        if st == SessionType.SSH:
            lines.append("")
            lines.append("── SSH Advanced ──")
            lines.append(f"Agent:           {'yes' if wizard.ssh_advanced_page.agent_cb.isChecked() else 'no'}")
            lines.append(f"Compression:     {'yes' if wizard.ssh_advanced_page.compression_cb.isChecked() else 'no'}")
            lines.append(f"Keep-alive:      {'yes' if wizard.ssh_advanced_page.keepalive_cb.isChecked() else 'no'}")
            lines.append(f"X11 forwarding:  {'yes' if wizard.ssh_advanced_page.x11_cb.isChecked() else 'no'}")
            proxy = wizard.ssh_advanced_page.proxy_input.text().strip()
            lines.append(f"Proxy command:   {proxy or '(none)'}")

        # RDP advanced
        if st == SessionType.RDP:
            lines.append("")
            lines.append("── RDP Advanced ──")
            gw = wizard.rdp_advanced_page.gateway_input.text().strip()
            lines.append(f"Gateway:         {gw or '(none)'}")
            lines.append(f"Drive redirect:  {'yes' if wizard.rdp_advanced_page.drive_cb.isChecked() else 'no'}")
            lines.append(f"Printer redirect:{'yes' if wizard.rdp_advanced_page.printer_cb.isChecked() else 'no'}")
            lines.append(f"Clipboard:       {'yes' if wizard.rdp_advanced_page.clipboard_cb.isChecked() else 'no'}")
            lines.append(f"Multi-monitor:   {'yes' if wizard.rdp_advanced_page.multimon_cb.isChecked() else 'no'}")
            c_idx = wizard.rdp_advanced_page.cert_combo.currentIndex()
            lines.append(f"Cert policy:     {wizard.rdp_advanced_page.cert_combo.itemData(c_idx) or 'auto'}")

        # VNC advanced
        if st == SessionType.VNC:
            lines.append("")
            lines.append("── VNC Advanced ──")
            lines.append(f"Scaling:         {'yes' if wizard.vnc_advanced_page.scaling_cb.isChecked() else 'no'}")
            lines.append(f"View-only:       {'yes' if wizard.vnc_advanced_page.viewonly_cb.isChecked() else 'no'}")
            c_idx2 = wizard.vnc_advanced_page.color_combo.currentIndex()
            lines.append(f"Color depth:     {wizard.vnc_advanced_page.color_combo.itemData(c_idx2) or '24'} bit")

        # Launch behaviour
        lines.append("")
        lines.append(f"Finish action:   {wizard.credential_page.launch_combo.currentText()}")

        self.summary_text.setText("\n".join(lines))
