"""Account manager UI — vault credential management."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QToolBar,
    QToolButton,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QLineEdit,
    QFormLayout,
    QLabel,
    QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal
from typing import Optional

from openadmindesk.core.account import Account
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.l10n import _


class AccountDialog(QDialog):
    """Dialog for adding/editing vault accounts."""

    def __init__(self, account: Optional[Account] = None, parent: Optional[QWidget] = None) -> None:
        """Initialize the account dialog.
        
        Args:
            account: Account to edit, or None for new account.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.account = account or Account()
        self.setWindowTitle(_("Edit Account") if account else _("Add Account"))
        self.setModal(True)
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_account()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Credentials")
        form.addRow(_("Name:"), self.name_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("root")
        form.addRow(_("Username:"), self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Optional password")
        form.addRow(_("Password:"), self.password_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_account(self) -> None:
        """Load account data into form fields."""
        if self.account:
            self.name_input.setText(self.account.name)
            self.username_input.setText(self.account.username)
            self.password_input.setText(self.account.password or "")



    def _validate_and_accept(self) -> None:
        """Validate form and accept if valid."""
        name = self.name_input.text().strip()
        username = self.username_input.text().strip()

        if not name:
            QMessageBox.warning(self, _("Validation"), _("Name is required."))
            return
        if not username:
            QMessageBox.warning(self, _("Validation"), _("Username is required."))
            return

        self.accept()

    def get_account(self) -> Account:
        """Get account from dialog data."""
        acct = self.account
        acct.name = self.name_input.text().strip()
        acct.username = self.username_input.text().strip()
        acct.password = self.password_input.text() or None
        return acct


class VaultStatusWidget(QWidget):
    """Widget showing vault lock status with actions."""

    def __init__(self, vault_manager: VaultManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.vault_manager = vault_manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("🔒 Vault Locked")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.action_button = QPushButton("Unlock...")
        layout.addWidget(self.action_button)

    def refresh(self) -> None:
        """Update status display."""
        if self.vault_manager.is_unlocked():
            self.status_label.setText("🔓 Vault Unlocked")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.action_button.setText("Lock")
        else:
            self.status_label.setText("🔒 Vault Locked")
            self.status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.action_button.setText("Unlock...")


class AccountManager(QWidget):
    """Vault account manager UI."""

    # Signals
    account_added = Signal(str)
    account_removed = Signal(str)
    vault_status_changed = Signal(bool)

    def __init__(self, vault_manager: VaultManager) -> None:
        """Initialize the account manager.
        
        Args:
            vault_manager: VaultManager instance.
        """
        super().__init__()
        self.vault_manager = vault_manager
        self._is_unlocked = False
        self._setup_ui()
        self._refresh_state()

    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Vault status
        self.vault_status = VaultStatusWidget(self.vault_manager)
        self.vault_status.action_button.clicked.connect(self._toggle_vault_lock)
        layout.addWidget(self.vault_status)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        add_btn = QToolButton()
        add_btn.setText("+ Add")
        add_btn.clicked.connect(self._add_account)
        add_btn.setEnabled(False)
        toolbar.addWidget(add_btn)
        self._add_btn = add_btn

        remove_btn = QToolButton()
        remove_btn.setText("− Remove")
        remove_btn.clicked.connect(self._remove_account)
        remove_btn.setEnabled(False)
        toolbar.addWidget(remove_btn)
        self._remove_btn = remove_btn

        refresh_btn = QToolButton()
        refresh_btn.setText("⟳ Refresh")
        refresh_btn.clicked.connect(self._load_accounts)
        toolbar.addWidget(refresh_btn)

        layout.addWidget(toolbar)

        # Account list
        self.account_list = QTreeWidget()
        self.account_list.setHeaderLabels(["Name", "Host", "Username", "Service"])
        self.account_list.setColumnWidth(0, 180)
        self.account_list.setColumnWidth(1, 160)
        self.account_list.setColumnWidth(2, 120)
        self.account_list.setColumnWidth(3, 80)
        self.account_list.setAlternatingRowColors(True)
        self.account_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.account_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.account_list)

        self.setMinimumSize(550, 350)

    def _toggle_vault_lock(self) -> None:
        """Toggle vault lock state with password prompt."""
        if self.vault_manager.is_unlocked():
            self.vault_manager.lock()
            self._refresh_state()
            self.vault_status_changed.emit(False)
        else:
            password, ok = QInputDialog.getText(
                self, _("Unlock Vault"), "Enter master password:",
                QLineEdit.Password
            )
            if ok and password:
                if self.vault_manager.unlock(password):
                    self._refresh_state()
                    self._load_accounts()
                    self.vault_status_changed.emit(True)
                else:
                    QMessageBox.critical(self, "Error",
                        "Wrong password or vault corrupted.")
            elif ok:
                # Password was entered via setup flow
                pass

    def _refresh_state(self) -> None:
        """Refresh UI state based on vault lock status."""
        unlocked = self.vault_manager.is_unlocked()
        self._is_unlocked = unlocked
        self._add_btn.setEnabled(unlocked)
        self._remove_btn.setEnabled(unlocked)
        self.vault_status.refresh()
        if not unlocked:
            self.account_list.clear()

    def setup_master_password(self) -> None:
        """Set up master password for the vault."""
        password, ok = QInputDialog.getText(
            self, "Setup Master Password",
            "Enter new master password:",
            QLineEdit.Password
        )
        if not ok or not password:
            return

        confirm, ok = QInputDialog.getText(
            self, "Confirm Master Password",
            "Confirm master password:",
            QLineEdit.Password
        )
        if not ok or password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return

        if self.vault_manager.setup_master_password(password):
            QMessageBox.information(self, "Success",
                "Vault created. Unlock it to manage accounts.")
            self._refresh_state()
        else:
            QMessageBox.critical(self, "Error",
                "Failed to create vault.")

    def _load_accounts(self) -> None:
        """Load accounts from vault into the list."""
        self.account_list.clear()

        if not self.vault_manager.is_unlocked():
            return

        accounts = self.vault_manager.get_all_accounts()
        for acc in accounts:
            item = QTreeWidgetItem([
                acc.name, acc.host, acc.username, acc.service_type
            ])
            item.setData(0, Qt.UserRole, acc.id)
            item.setToolTip(0, f"ID: {acc.id}")
            self.account_list.addTopLevelItem(item)

    def _add_account(self) -> None:
        """Add a new vault account."""
        dialog = AccountDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            account = dialog.get_account()
            if self.vault_manager.add_account(account):
                self._load_accounts()
                self.account_added.emit(account.id)
            else:
                QMessageBox.critical(self, "Error", "Failed to save account.")

    def _edit_account(self, account_id: str) -> None:
        """Edit an existing vault account."""
        account = self.vault_manager.get_account(account_id)
        if not account:
            return

        dialog = AccountDialog(account, parent=self)
        if dialog.exec() == QDialog.Accepted:
            # Remove old, add updated
            if self.vault_manager.remove_account(account_id):
                updated = dialog.get_account()
                # Preserve original ID
                updated.id = account_id
                if self.vault_manager.add_account(updated):
                    self._load_accounts()
                    self.account_added.emit(account_id)

    def _remove_account(self) -> None:
        """Remove selected account."""
        selected = self.account_list.currentItem()
        if not selected:
            return

        account_id = selected.data(0, Qt.UserRole)
        account_name = selected.text(0)

        reply = QMessageBox.question(
            self, "Remove Account",
            f"Remove '{account_name}' from vault?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.vault_manager.remove_account(account_id):
                self._load_accounts()
                self.account_removed.emit(account_id)
            else:
                QMessageBox.critical(self, "Error", "Failed to remove account.")

    def _show_context_menu(self, position) -> None:
        """Show context menu for account list."""
        item = self.account_list.itemAt(position)
        if not item or not self.vault_manager.is_unlocked():
            return

        from PySide6.QtWidgets import QMenu
        try:
            from PySide6.QtGui import QAction  # PySide6 >= 6.11
        except ImportError:
            from PySide6.QtWidgets import QAction  # PySide6 < 6.11
        menu = QMenu()

        edit_action = QAction(_("Edit"), self)
        account_id = item.data(0, Qt.UserRole)
        edit_action.triggered.connect(lambda: self._edit_account(account_id))
        menu.addAction(edit_action)

        remove_action = QAction(_("Remove"), self)
        remove_action.triggered.connect(self._remove_account)
        menu.addAction(remove_action)

        menu.exec(self.account_list.mapToGlobal(position))
