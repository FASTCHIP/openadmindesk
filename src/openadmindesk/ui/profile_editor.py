"""Profile editor widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QHBoxLayout, QMessageBox,
    QComboBox, QFileDialog, QTextEdit,
)
from PySide6.QtCore import QSize, Signal
from typing import Optional

from openadmindesk.core.account import Account
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_validation import validate_profile
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.l10n import _
from openadmindesk.ui.session_icons import (
    default_icon_id_for_session_type,
    icon_options,
    session_icon,
)


class ProfileEditor(QWidget):
    """Widget for editing profiles."""
    
    # Signals
    profile_saved = Signal(str)
    profile_cancelled = Signal()
    
    def __init__(self, profile: Optional[Profile] = None, store: Optional[ProfileStore] = None,
                 vault_manager: Optional[VaultManager] = None) -> None:
        """Initialize the profile editor.
        
        Args:
            profile: Profile to edit. Creates new one if None.
            store: ProfileStore for persistence. If None, editing is in-memory only.
            vault_manager: VaultManager for credential auto-fill. Optional.
        """
        super().__init__()
        self.profile = profile or Profile()
        self.store = store
        self.vault_manager = vault_manager
        self._setup_ui()
        self._load_profile()
        self._load_vault_accounts()
        self.setWindowTitle(f"Profile: {self.profile.name}")
    
    def _setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        
        # Form layout for profile fields
        form_layout = QFormLayout()
        self._form_layout = form_layout
        
        # Vault account selector (if vault manager provided)
        self.vault_account_selector = QComboBox()
        self.vault_account_selector.addItem(_("(none — manual entry)"), "")
        self.vault_account_selector.currentIndexChanged.connect(
            self._on_vault_account_selected
        )
        if self.vault_manager:
            form_layout.addRow(_("Vault Account:"), self.vault_account_selector)
        
        # Name field
        self.name_input = QLineEdit()
        form_layout.addRow(_("Name:"), self.name_input)
        
        # Host field
        self.host_input = QLineEdit()
        form_layout.addRow(_("Host:"), self.host_input)
        
        # Port field
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        form_layout.addRow(_("Port:"), self.port_input)
        
        # Session type
        self.session_type_input = QComboBox()
        self.session_type_input.setIconSize(QSize(20, 20))
        self.session_type_input.addItem(session_icon("ssh"), "SSH", SessionType.SSH)
        self.session_type_input.addItem(session_icon("telnet"), "Telnet", SessionType.TELNET)
        self.session_type_input.addItem(session_icon("rdp"), "RDP", SessionType.RDP)
        self.session_type_input.currentIndexChanged.connect(
            self._on_session_type_changed
        )
        form_layout.addRow(_("Type:"), self.session_type_input)

        # Session icon
        self.icon_input = QComboBox()
        self.icon_input.setIconSize(QSize(20, 20))
        for spec in icon_options():
            self.icon_input.addItem(session_icon(spec.icon_id), spec.label, spec.icon_id)
        form_layout.addRow(_("Session Icon:"), self.icon_input)
        
        # Username field
        self.username_input = QLineEdit()
        form_layout.addRow(_("Username:"), self.username_input)
        
        # Password field
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow(_("Password:"), self.password_input)
        
        # Private key path with Browse button
        self.key_row_widget = QWidget()
        key_layout = QHBoxLayout(self.key_row_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.private_key_input = QLineEdit()
        self.private_key_input.setPlaceholderText(_("Optional - leave empty for password login"))
        key_browse = QPushButton(_("Browse..."))
        key_browse.clicked.connect(self._browse_private_key)
        key_layout.addWidget(self.private_key_input)
        key_layout.addWidget(key_browse)
        form_layout.addRow(_("Private Key:"), self.key_row_widget)
        
        # Key passphrase
        self.key_passphrase_input = QLineEdit()
        self.key_passphrase_input.setEchoMode(QLineEdit.Password)
        self.key_passphrase_input.setPlaceholderText("Optional passphrase")
        form_layout.addRow(_("Key Passphrase:"), self.key_passphrase_input)
        
        # Proxy / Jump host
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("e.g. user@jump-host:22 or ssh -W %h:%p jump")
        form_layout.addRow(_("Proxy / Jump Host:"), self.proxy_input)
        
        # SSH agent checkbox
        self.use_ssh_agent_checkbox = QCheckBox(_("Use SSH Agent"))
        form_layout.addRow("", self.use_ssh_agent_checkbox)
        
        # Compression checkbox
        self.compression_checkbox = QCheckBox(_("Enable Compression"))
        form_layout.addRow("", self.compression_checkbox)
        
        # Keep alive checkbox
        self.keep_alive_checkbox = QCheckBox(_("Keep Alive"))
        self.keep_alive_checkbox.setChecked(True)
        form_layout.addRow("", self.keep_alive_checkbox)
        
        # ── RDP options ───────────────────────────────────────────────────
        self.rdp_multimon_check = QCheckBox(_("Use All Monitors"))
        form_layout.addRow("", self.rdp_multimon_check)
        
        self.rdp_drive_check = QCheckBox(_("Enable Drive Redirection"))
        form_layout.addRow("", self.rdp_drive_check)
        
        self.rdp_drive_path_input = QLineEdit()
        self.rdp_drive_path_input.setPlaceholderText("/home/user  or  C:\\Users\\...")
        form_layout.addRow(_("Shared Path:"), self.rdp_drive_path_input)
        
        self.rdp_printer_check = QCheckBox(_("Enable Printer Redirection"))
        form_layout.addRow("", self.rdp_printer_check)
        
        self.rdp_gateway_input = QLineEdit()
        self.rdp_gateway_input.setPlaceholderText("gateway.example.com")
        form_layout.addRow(_("TS Gateway:"), self.rdp_gateway_input)
        
        self.rdp_gateway_account_selector = QComboBox()
        self.rdp_gateway_account_selector.addItem(_("(none — manual gateway)"), "")
        self.rdp_gateway_account_selector.currentIndexChanged.connect(
            self._on_rdp_gateway_account_selected
        )
        if self.vault_manager:
            form_layout.addRow(_("Gateway Vault Account:"), self.rdp_gateway_account_selector)

        self.rdp_gateway_user_input = QLineEdit()
        self.rdp_gateway_user_input.setPlaceholderText("domain\\user")
        form_layout.addRow(_("Gateway User:"), self.rdp_gateway_user_input)
        
        self.rdp_gateway_pass_input = QLineEdit()
        self.rdp_gateway_pass_input.setEchoMode(QLineEdit.Password)
        self.rdp_gateway_pass_input.setPlaceholderText("Optional")
        form_layout.addRow(_("Gateway Pass:"), self.rdp_gateway_pass_input)
        
        self._rdp_widgets = [
            self.rdp_multimon_check, self.rdp_drive_check,
            self.rdp_drive_path_input, self.rdp_printer_check,
            self.rdp_gateway_input, self.rdp_gateway_account_selector,
            self.rdp_gateway_user_input, self.rdp_gateway_pass_input,
        ]
        
        # Notes field
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Server description, notes, contact info...")
        self.notes_input.setMaximumHeight(60)
        form_layout.addRow("Notes:", self.notes_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton(_("Save"))
        self.save_button.clicked.connect(self._save_profile)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self._cancel_editing)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # Set minimum size
        self.setMinimumSize(400, 300)
    
    def _load_vault_accounts(self) -> None:
        """Load vault accounts into the selector combo box."""
        if not self.vault_manager or not self.vault_manager.is_unlocked():
            return
        
        accounts = self.vault_manager.get_all_accounts()
        for acc in accounts:
            label = f"{acc.name} ({acc.username}@{acc.host})"
            self.vault_account_selector.addItem(label, acc.id)
            self.rdp_gateway_account_selector.addItem(label, acc.id)
        if self.profile.credential_id:
            index = self.vault_account_selector.findData(self.profile.credential_id)
            if index >= 0:
                self.vault_account_selector.setCurrentIndex(index)
        if self.profile.rdp_gateway_credential_id:
            index = self.rdp_gateway_account_selector.findData(
                self.profile.rdp_gateway_credential_id
            )
            if index >= 0:
                self.rdp_gateway_account_selector.setCurrentIndex(index)
    
    def _on_vault_account_selected(self, index: int) -> None:
        """Handle vault account selection to auto-fill profile fields."""
        if not self.vault_manager or not self.vault_manager.is_unlocked():
            return
        
        account_id = self.vault_account_selector.itemData(index)
        if not account_id:
            return
        
        account = self.vault_manager.get_account(account_id)
        if not account:
            return
        
        # Auto-fill profile fields from vault account
        if account.host and not self.host_input.text():
            self.host_input.setText(account.host)
        if account.port:
            self.port_input.setValue(account.port)
        if account.username and not self.username_input.text():
            self.username_input.setText(account.username)
        self.profile.credential_id = account.id
        self.password_input.clear()
        self.key_passphrase_input.clear()
        self.rdp_gateway_pass_input.clear()

    def _on_rdp_gateway_account_selected(self, index: int) -> None:
        """Fill TS Gateway fields from a selected vault account."""
        if not self.vault_manager or not self.vault_manager.is_unlocked():
            return

        account_id = self.rdp_gateway_account_selector.itemData(index)
        if not account_id:
            return

        account = self.vault_manager.get_account(account_id)
        if not account:
            return

        if account.host and not self.rdp_gateway_input.text():
            self.rdp_gateway_input.setText(account.host)
        if account.username and not self.rdp_gateway_user_input.text():
            self.rdp_gateway_user_input.setText(account.username)
        self.profile.rdp_gateway_credential_id = account.id
        self.rdp_gateway_pass_input.clear()

    def _on_session_type_changed(self, index: int) -> None:
        """Update port and UI when session type changes."""
        st = self.session_type_input.itemData(index)
        if st == SessionType.RDP:
            if self.port_input.value() == 22:
                self.port_input.setValue(3389)
            self._set_ssh_fields_visible(False)
            self._set_rdp_fields_visible(True)
        elif st == SessionType.TELNET:
            if self.port_input.value() == 22:
                self.port_input.setValue(23)
            self._set_ssh_fields_visible(False)
            self._set_rdp_fields_visible(False)
        else:
            if self.port_input.value() in (23, 3389):
                self.port_input.setValue(22)
            self._set_ssh_fields_visible(True)
            self._set_rdp_fields_visible(False)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form_layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _set_ssh_fields_visible(self, visible: bool) -> None:
        for widget in [
            self.keep_alive_checkbox,
            self.use_ssh_agent_checkbox,
            self.compression_checkbox,
            self.key_row_widget,
            self.key_passphrase_input,
            self.proxy_input,
        ]:
            self._set_row_visible(widget, visible)

    def _set_rdp_fields_visible(self, visible: bool) -> None:
        for widget in self._rdp_widgets:
            self._set_row_visible(widget, visible)
    
    def _browse_private_key(self) -> None:
        """Open file dialog to select an SSH private key."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SSH Private Key",
            self.private_key_input.text() or "",
            "SSH Keys (*.pem *.key *id_*);;All Files (*)"
        )
        if path:
            self.private_key_input.setText(path)
    
    def _load_profile(self) -> None:
        """Load profile data into UI."""
        self.name_input.setText(self.profile.name)
        self.host_input.setText(self.profile.host)
        self.port_input.setValue(self.profile.port)
        self.username_input.setText(self.profile.username)
        self.password_input.clear()
        if self.profile.password or self.profile.credential_id:
            self.password_input.setPlaceholderText(
                _("Saved password is retained; enter a new password to change")
            )
        else:
            self.password_input.setPlaceholderText("")
        self.private_key_input.setText(self.profile.private_key_path or "")
        self.key_passphrase_input.clear()
        self.proxy_input.setText(self.profile.proxy_command or "")
        self.use_ssh_agent_checkbox.setChecked(self.profile.use_ssh_agent)
        self.compression_checkbox.setChecked(self.profile.compression)
        self.keep_alive_checkbox.setChecked(self.profile.keep_alive)
        # RDP fields
        self.rdp_multimon_check.setChecked(self.profile.rdp_multimon)
        self.rdp_drive_check.setChecked(self.profile.rdp_drive_redirection)
        self.rdp_drive_path_input.setText(self.profile.rdp_drive_path or "")
        self.rdp_printer_check.setChecked(self.profile.rdp_printer_redirection)
        self.rdp_gateway_input.setText(self.profile.rdp_gateway or "")
        self.rdp_gateway_user_input.setText(self.profile.rdp_gateway_username or "")
        self.rdp_gateway_pass_input.clear()
        self.notes_input.setPlainText(self.profile.notes or "")
        
        # Set session type
        for i in range(self.session_type_input.count()):
            if self.session_type_input.itemData(i) == self.profile.session_type:
                self.session_type_input.setCurrentIndex(i)
                break
        icon_id = self.profile.icon_id or default_icon_id_for_session_type(
            self.profile.session_type
        )
        icon_index = self.icon_input.findData(icon_id)
        if icon_index >= 0:
            self.icon_input.setCurrentIndex(icon_index)
        self._on_session_type_changed(self.session_type_input.currentIndex())
    
    def _save_profile(self) -> None:
        """Save the profile."""
        # Get values from UI
        self.profile.name = self.name_input.text().strip()
        self.profile.host = self.host_input.text().strip()
        self.profile.port = self.port_input.value()
        self.profile.session_type = self.session_type_input.currentData()
        self.profile.icon_id = self.icon_input.currentData() or None
        self.profile.username = self.username_input.text().strip()
        self.profile.private_key_path = self.private_key_input.text().strip() or None
        selected_credential_id = self.vault_account_selector.currentData() or None
        selected_gateway_credential_id = (
            self.rdp_gateway_account_selector.currentData() or None
        )
        entered_password = self.password_input.text() or None
        entered_key_passphrase = self.key_passphrase_input.text() or None
        entered_gateway_password = self.rdp_gateway_pass_input.text() or None
        
        # Determine vault_unlocked
        vault_unlocked = self.vault_manager and self.vault_manager.is_unlocked()
        
        # 1) Any newly entered primary/gateway secret with vault absent/locked => QMessageBox.critical `Vault Required`, return before store/signal/close; never copy entered secret into Profile.
        if ((entered_password or entered_key_passphrase) or entered_gateway_password) and not vault_unlocked:
            QMessageBox.critical(self, _("Vault Required"), _("Cannot save profile with new secrets without an unlocked vault."))
            return
            
        # 2) Legacy existing profile plaintext with no matching selected credential ID and no newly entered replacement => critical migration-required, return; no silent loss.
        if (self.profile.password or self.profile.private_key_passphrase or self.profile.rdp_gateway_password) and not selected_credential_id:
            # Check if we have new secrets that would replace the old ones
            has_new_secrets = (entered_password or entered_key_passphrase or entered_gateway_password)
            if not has_new_secrets:
                QMessageBox.critical(self, _("Migration Required"), _("Legacy profile with plaintext secrets requires a credential ID or new secret to be saved."))
                return
        
        # 3) Unlocked entered primary: upsert Account via add_account directly, NEVER remove_account. If selected ID, get existing account and preserve password/passphrase counterpart when that field left blank; new field overrides. add False => critical Vault Error, return before store.
        if (entered_password or entered_key_passphrase) and vault_unlocked:
            # Get existing account if we have a selected credential ID
            existing_account = None
            if selected_credential_id:
                existing_account = self.vault_manager.get_account(selected_credential_id)
            
            # Create account with appropriate password/passphrase handling
            account = Account(
                id=selected_credential_id,
                name=self.profile.name or self.name_input.text().strip(),
                username=self.profile.username,
                password=entered_password if entered_password is not None else (existing_account.password if existing_account else ""),
                private_key_passphrase=entered_key_passphrase if entered_key_passphrase is not None else (existing_account.private_key_passphrase if existing_account else None),
                host=self.host_input.text().strip(),
                port=self.port_input.value(),
                service_type=self.session_type_input.currentData().value,
            )
            
            # Add account (this will upsert)
            if not self.vault_manager.add_account(account):
                QMessageBox.critical(self, _("Vault Error"), _("Failed to save account to vault."))
                return
                
            # Update selected credential ID if it was newly created
            if not selected_credential_id:
                selected_credential_id = account.id
                
        # 4) Gateway entered: same direct upsert; preserve selected account data where appropriate; failure returns.
        if entered_gateway_password and vault_unlocked:
            # Get existing gateway account if we have a selected credential ID
            existing_gateway_account = None
            if selected_gateway_credential_id:
                existing_gateway_account = self.vault_manager.get_account(selected_gateway_credential_id)
                
            gateway_account = Account(
                id=selected_gateway_credential_id,
                name=f"{self.profile.name or self.name_input.text().strip()} Gateway",
                username=self.rdp_gateway_user_input.text().strip(),
                password=entered_gateway_password if entered_gateway_password is not None else (existing_gateway_account.password if existing_gateway_account else ""),
                host=self.rdp_gateway_input.text().strip(),
                port=443,
                service_type="rdp-gateway",
            )
            
            # Add gateway account (this will upsert)
            if not self.vault_manager.add_account(gateway_account):
                QMessageBox.critical(self, _("Vault Error"), _("Failed to save gateway account to vault."))
                return
                
            # Update selected gateway credential ID if it was newly created
            if not selected_gateway_credential_id:
                selected_gateway_credential_id = gateway_account.id

        self.profile.credential_id = selected_credential_id
        self.profile.rdp_gateway_credential_id = selected_gateway_credential_id
        
        # 5) Selected credential ID means Profile primary secrets set None regardless current vault lock; selected gateway ID means gateway password None. Existing selected ID + no new secret must save safely while locked.
        if selected_credential_id:
            self.profile.password = None
            self.profile.private_key_passphrase = None
        else:
            # If no credential ID, preserve existing passwords
            password = entered_password if entered_password is not None else self.profile.password
            key_passphrase = entered_key_passphrase if entered_key_passphrase is not None else self.profile.private_key_passphrase
            self.profile.password = password
            self.profile.private_key_passphrase = key_passphrase
            
        self.profile.proxy_command = self.proxy_input.text().strip() or None
        self.profile.use_ssh_agent = self.use_ssh_agent_checkbox.isChecked()
        self.profile.compression = self.compression_checkbox.isChecked()
        self.profile.keep_alive = self.keep_alive_checkbox.isChecked()
        if self.profile.session_type == SessionType.RDP:
            self.profile.rdp_multimon = self.rdp_multimon_check.isChecked()
            self.profile.rdp_drive_redirection = self.rdp_drive_check.isChecked()
            self.profile.rdp_drive_path = self.rdp_drive_path_input.text().strip() or None
            self.profile.rdp_printer_redirection = self.rdp_printer_check.isChecked()
            self.profile.rdp_gateway = self.rdp_gateway_input.text().strip() or None
            self.profile.rdp_gateway_username = self.rdp_gateway_user_input.text().strip() or None
            self.profile.rdp_gateway_credential_id = selected_gateway_credential_id
            if selected_gateway_credential_id:
                self.profile.rdp_gateway_password = None
            else:
                gateway_password = entered_gateway_password if entered_gateway_password is not None else self.profile.rdp_gateway_password
                self.profile.rdp_gateway_password = gateway_password
        else:
            self.profile.rdp_multimon = False
            self.profile.rdp_drive_redirection = False
            self.profile.rdp_drive_path = None
            self.profile.rdp_printer_redirection = False
            self.profile.rdp_gateway = None
            self.profile.rdp_gateway_username = None
            self.profile.rdp_gateway_password = None
            self.profile.rdp_gateway_credential_id = None
        self.profile.notes = self.notes_input.toPlainText().strip()
        
        # Validate profile
        is_valid, error = validate_profile(self.profile)
        if not is_valid:
            QMessageBox.critical(self, _("Validation Error"), error)
            return
        
        # Save to store if available
        if self.store:
            if not self.store.save_profile(self.profile):
                QMessageBox.critical(self, _("Save Error"), _("Failed to save profile to database"))
                return
        
        # Emit signal that profile was saved
        self.profile_saved.emit(self.profile.name)
        
        # Close the editor
        self.close()
    
    def _cancel_editing(self) -> None:
        """Cancel editing."""
        self.profile_cancelled.emit()
        self.close()
