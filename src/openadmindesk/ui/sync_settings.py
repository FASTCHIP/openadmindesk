"""Sync settings dialog — configure cloud sync for OpenAdminDesk."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QCheckBox,
)
from typing import Optional

from openadmindesk.core.sync_manager import SyncManager, ConflictMode
from openadmindesk.core.l10n import _


class SyncSettingsDialog(QDialog):
    """Dialog for configuring cloud sync."""

    def __init__(self, sync_manager: SyncManager, parent=None) -> None:
        super().__init__(parent)
        self.sync = sync_manager
        self.setWindowTitle(_(_("Cloud Sync Settings")))
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Enable checkbox ───────────────────────────────────────────────
        self.enable_check = QCheckBox(_("Enable cloud sync"))
        self.enable_check.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_check)

        # ── Folder ────────────────────────────────────────────────────────
        folder_group = QGroupBox(_("Sync Folder"))
        folder_layout = QHBoxLayout(folder_group)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText(
            _("e.g. /home/user/Google Drive/MySync  or  C:\\Users\\...\\Google Drive\\MySync")
        )
        folder_layout.addWidget(self.folder_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)

        layout.addWidget(folder_group)

        # ── Password ──────────────────────────────────────────────────────
        pwd_group = QGroupBox(_("Encryption Password"))
        pwd_form = QFormLayout(pwd_group)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText(_("Set a strong sync password"))
        pwd_form.addRow("Password:", self.pwd_input)

        self.pwd_confirm = QLineEdit()
        self.pwd_confirm.setEchoMode(QLineEdit.Password)
        self.pwd_confirm.setPlaceholderText(_("Confirm password"))
        pwd_form.addRow("Confirm:", self.pwd_confirm)

        layout.addWidget(pwd_group)

        # ── Conflict mode ─────────────────────────────────────────────────
        mode_group = QGroupBox(_("Conflict Resolution"))
        mode_layout = QFormLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(_("Merge — keep both, rename duplicates"), ConflictMode.MERGE.value)
        self.mode_combo.addItem(_("Replace local — overwrite with cloud"), ConflictMode.REPLACE_LOCAL.value)
        self.mode_combo.addItem(_("Separate — import into separate folder"), ConflictMode.SEPARATE.value)
        mode_layout.addRow(_("When pulling:"), self.mode_combo)

        layout.addWidget(mode_group)

        # ── Status ────────────────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #969696;")
        layout.addWidget(self.status_label)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        self.sync_now_btn = QPushButton(_("🔄 Sync Now"))
        self.sync_now_btn.clicked.connect(self._sync_now)
        btn_layout.addWidget(self.sync_now_btn)

        self.push_btn = QPushButton(_("⬆ Push to Cloud"))
        self.push_btn.clicked.connect(self._push_now)
        btn_layout.addWidget(self.push_btn)

        self.pull_btn = QPushButton(_("⬇ Pull from Cloud"))
        self.pull_btn.clicked.connect(self._pull_now)
        btn_layout.addWidget(self.pull_btn)

        layout.addLayout(btn_layout)

        # ── OK/Cancel ────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_enable_toggled(self, checked: bool) -> None:
        enabled = checked
        # Hide/show all content groups
        for w in self.findChildren(QGroupBox):
            w.setEnabled(enabled)
        for w in self.findChildren(QPushButton):
            if w not in [b for b in self.findChildren(QDialogButtonBox)]:
                w.setEnabled(enabled)
        self.sync_now_btn.setEnabled(enabled)
        self.push_btn.setEnabled(enabled)
        self.pull_btn.setEnabled(enabled)

    def _load_config(self) -> None:
        cfg = self.sync.config
        self.enable_check.setChecked(cfg.enabled)
        self.folder_input.setText(cfg.sync_folder)
        if cfg.sync_password_hash:
            self.pwd_input.setText("••••••••")
            self.pwd_input.setToolTip(_("Password is set. Enter new to change."))
        # Select conflict mode
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == cfg.conflict_mode:
                self.mode_combo.setCurrentIndex(i)
                break
        self._update_status()
        self._on_enable_toggled(cfg.enabled)

    def _update_status(self) -> None:
        cfg = self.sync.config
        if not cfg.enabled:
            self.status_label.setText(_("Sync is disabled."))
            return
        msgs = []
        if cfg.last_push_at:
            import datetime
            t = datetime.datetime.fromtimestamp(cfg.last_push_at)
            msgs.append(f"Last push: {t.strftime('%Y-%m-%d %H:%M')}")
        if cfg.last_pull_at:
            t = datetime.datetime.fromtimestamp(cfg.last_pull_at)
            msgs.append(f"Last pull: {t.strftime('%Y-%m-%d %H:%M')}")
        self.status_label.setText(" | ".join(msgs) if msgs else _("No sync performed yet."))

    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, _("Select Cloud Sync Folder"),
            self.folder_input.text() or "",
        )
        if path:
            self.folder_input.setText(path)

    def _get_password(self) -> Optional[str]:
        pwd = self.pwd_input.text()
        if pwd.startswith("••••"):
            # Password unchanged — use stored hash to validate later
            return None  # caller should handle "no new password"
        confirm = self.pwd_confirm.text()
        if pwd != confirm:
            QMessageBox.warning(self, _("Error"), _("Passwords do not match."))
            return None
        if len(pwd) < 8:
            QMessageBox.warning(self, _("Error"), "Sync password must be at least 8 characters.")
            return None
        return pwd

    def _sync_now(self) -> None:
        pwd = self._get_password()
        if pwd is None and not self.sync.config.sync_password_hash:
            QMessageBox.warning(self, _("Error"), _("Enter a sync password first."))
            return
        # If password unchanged, we need the stored one — but we can't recover it.
        # For sync operations, user must re-enter password.
        if pwd is None:
            QMessageBox.warning(self, _("Error"),
                _("Re-enter your sync password to perform sync operations."))
            return
        result = self.sync.auto_sync(pwd)
        if result:
            self.status_label.setText(result)
        else:
            self.status_label.setText(_("Sync complete — no changes detected."))

    def _push_now(self) -> None:
        pwd = self._get_password()
        if pwd is None:
            QMessageBox.warning(self, _("Error"), _("Re-enter your sync password to push."))
            return
        ok = self.sync.push(pwd)
        self.status_label.setText(_("✅ Pushed to cloud.") if ok else _("❌ Push failed."))
        self._update_status()

    def _pull_now(self) -> None:
        pwd = self._get_password()
        if pwd is None:
            QMessageBox.warning(self, _("Error"), _("Re-enter your sync password to pull."))
            return
        result = self.sync.pull(pwd)
        self.status_label.setText(result or _("No changes pulled."))
        self._update_status()

    def _on_accept(self) -> None:
        if not self.enable_check.isChecked():
            self.sync.disable()
            self.accept()
            return

        folder = self.folder_input.text().strip()
        if not folder:
            QMessageBox.warning(self, _("Error"), _("Select a sync folder."))
            return

        pwd = self._get_password()
        if pwd is None:
            if not self.sync.config.sync_password_hash:
                QMessageBox.warning(self, _("Error"),
                    _("Enter a sync password to enable encryption.") + "\n" +
                    _("This password protects your data in the cloud."))
                return
            # Keep existing password, just update folder/mode
            pwd = ""  # won't be used for hashing

        mode = self.mode_combo.currentData()
        self.sync.configure(folder, pwd if pwd else "", mode)
        self.accept()
