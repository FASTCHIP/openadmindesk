"""Main application window."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QDialog, QInputDialog, QLineEdit,
    QFileDialog, QToolBar, QPushButton, QSpinBox, QDockWidget,
    QFormLayout, QDialogButtonBox,
)
try:
    from PySide6.QtGui import QAction  # PySide6 >= 6.11
except ImportError:
    from PySide6.QtWidgets import QAction  # PySide6 < 6.11
from PySide6.QtCore import Qt, QTimer
import os
from pathlib import Path

from openadmindesk.ui.activity_rail import ActivityRail
from openadmindesk.ui.connection_tree import ConnectionTree
from openadmindesk.ui.workspace_container import WorkspaceContainer
from openadmindesk.ui.quick_connect_toolbar import QuickConnectToolbar
from openadmindesk.ui.connection_event_area import ConnectionEventArea
from openadmindesk.ui.multi_exec_panel import MultiExecPanel
from openadmindesk.ui.profile_editor import ProfileEditor
from openadmindesk.ui.account_manager import AccountManager
from openadmindesk.ui.tunnel_manager import TunnelManagerWidget
from openadmindesk.ui.snippet_manager import SnippetManagerWidget
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.settings import SettingsStore
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.sync_manager import SyncManager
from openadmindesk.platform.platform_utils import default_db_path, default_vault_path, is_portable
from openadmindesk.core.l10n import _
from openadmindesk.core.vault_upgrade import (
    inspect_vault_version,
    upgrade_vault_v1_to_v2,
    VaultUpgradeError,
)

from typing import Optional
import copy
import logging
logger = logging.getLogger(__name__)

VAULT_POLL_INTERVAL_MS = 1000


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle(_("OpenAdminDesk"))
        if is_portable():
            self.setWindowTitle(_("OpenAdminDesk") + " [PORTABLE]")

        # Core services (platform-appropriate paths)
        self.profile_store = ProfileStore(default_db_path())
        self.vault_manager = VaultManager(default_vault_path())
        self.sync_manager = SyncManager(self.profile_store, self.vault_manager)

        # Settings
        self._settings_store = SettingsStore()
        self._app_settings = self._settings_store.load()
        self.resize(
            self._app_settings.window_width,
            self._app_settings.window_height,
        )

        # Broadcast mode
        self.broadcast_mode = False

        # Workspace layout
        self.workspace_layout = "single"

        # Build UI
        self._setup_central_widget()
        self._setup_quick_connect_toolbar()
        self._setup_view_toolbar()
        self._setup_status_bar()
        self._setup_menu_bar()
        self._connect_signals()

        # Load profiles into tree
        self.connection_tree.refresh()

        # Vault auto-lock polling timer
        self._last_vault_unlocked = self.vault_manager.is_unlocked()
        self._vault_lock_timer = QTimer(self)
        self._vault_lock_timer.setInterval(VAULT_POLL_INTERVAL_MS)
        self._vault_lock_timer.timeout.connect(self._poll_vault_lock_state)
        self._vault_lock_timer.start()

        # First-run: prompt to set up vault if none exists
        QTimer.singleShot(500, self._maybe_prompt_first_vault_setup)

    def _maybe_prompt_first_vault_setup(self) -> None:
        """If no vault exists, offer to set one up on first run."""
        if not os.path.exists(self.vault_manager.vault_path):
            reply = QMessageBox.question(
                self, "Welcome to OpenAdminDesk",
                "No vault found. A vault is required to store credentials.\n"
                "Set up a master password now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._setup_vault()

    def _connect_signals(self) -> None:
        """Wire up signals between components."""
        # Quick connect → open SSH tab
        self.quick_connect_toolbar.connect_requested.connect(
            self._on_quick_connect
        )
        # Connection tree → open session or edit/delete
        self.connection_tree.connection_requested.connect(
            self._open_ssh_tab
        )
        self.connection_tree.profile_edit_requested.connect(
            self._on_profile_edit_requested
        )
        self.connection_tree.profile_delete_requested.connect(
            self._on_profile_delete_requested
        )
        self.connection_tree.profile_duplicate_requested.connect(
            self._on_profile_duplicate_requested
        )
        self.connection_tree.profile_export_requested.connect(
            self._on_profile_export_requested
        )
        self.connection_tree.profile_sftp_requested.connect(
            self._on_profile_sftp_requested
        )
        self.connection_tree.folder_launch_requested.connect(
            self._on_folder_launch_requested
        )
        # Connection tree → new session from context menu
        self.connection_tree.new_profile_requested = (
            self._on_new_session_requested
        )
        # Tab changes → update status bar
        # Connect signals from all workspaces
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            ws.tabCloseRequested.connect(
                lambda i: self._update_status_bar_sessions()
            )
            ws.currentChanged.connect(
                lambda i: self._update_status_bar_sessions()
            )

        # Activity rail mode changes
        self.activity_rail.mode_changed.connect(self._on_activity_mode_changed)

    def _setup_central_widget(self) -> None:
        """Setup the main content area with activity rail and workspace."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with activity rail and workspace
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Connection tree (will be set as sessions widget)
        self.connection_tree = ConnectionTree(self.profile_store)

        # Activity rail (left sidebar)
        self.activity_rail = ActivityRail()

        # Workspace container (main area) - manages multiple panes
        self.workspace_container = WorkspaceContainer()
        self.workspace_container.set_new_session_callback(self._on_new_session_requested)

        # Set up sessions widget in activity rail
        self.activity_rail.set_sessions_widget(self.connection_tree)

        main_layout.addWidget(self.activity_rail)
        main_layout.addWidget(self.workspace_container)
        main_layout.setStretch(1, 1)  # Let workspace expand

    def _setup_quick_connect_toolbar(self) -> None:
        """Setup the quick connect toolbar."""
        self.quick_connect_toolbar = QuickConnectToolbar()
        self.addToolBar(self.quick_connect_toolbar)

    def _setup_view_toolbar(self) -> None:
        """Setup the view toolbar with split workspace controls."""
        self.view_toolbar = QToolBar(_("View"))
        self.view_toolbar.setMovable(False)

        # Split layout buttons
        self.split_single_btn = QPushButton(_("1: Single"))
        self.split_single_btn.setCheckable(True)
        self.split_single_btn.setToolTip(_("Single workspace"))
        self.split_single_btn.clicked.connect(lambda: self._set_workspace_layout("single"))
        self.view_toolbar.addWidget(self.split_single_btn)

        self.split_horizontal_btn = QPushButton(_("2: Horizontal"))
        self.split_horizontal_btn.setCheckable(True)
        self.split_horizontal_btn.setToolTip(_("Two horizontal workspaces"))
        self.split_horizontal_btn.clicked.connect(lambda: self._set_workspace_layout("horizontal"))
        self.view_toolbar.addWidget(self.split_horizontal_btn)

        self.split_vertical_btn = QPushButton(_("2: Vertical"))
        self.split_vertical_btn.setCheckable(True)
        self.split_vertical_btn.setToolTip(_("Two vertical workspaces"))
        self.split_vertical_btn.clicked.connect(lambda: self._set_workspace_layout("vertical"))
        self.view_toolbar.addWidget(self.split_vertical_btn)

        self.split_grid_btn = QPushButton(_("4: Grid"))
        self.split_grid_btn.setCheckable(True)
        self.split_grid_btn.setToolTip(_("Four workspace grid"))
        self.split_grid_btn.clicked.connect(lambda: self._set_workspace_layout("grid"))
        self.view_toolbar.addWidget(self.split_grid_btn)

        # Set default layout
        self.split_single_btn.setChecked(True)

        self.view_toolbar.addSeparator()

        self.multi_exec_btn = QPushButton(_("📢 MultiExec"))
        self.multi_exec_btn.setCheckable(True)
        self.multi_exec_btn.setToolTip(_("Show/hide MultiExec panel for broadcast keystrokes"))
        self.multi_exec_btn.clicked.connect(self._toggle_multi_exec_panel)
        self.view_toolbar.addWidget(self.multi_exec_btn)

        self.addToolBar(Qt.TopToolBarArea, self.view_toolbar)

        # MultiExec panel (dock widget, right side)
        self._multi_exec_panel = MultiExecPanel()
        self._multi_exec_dock = QDockWidget(_("MultiExec"), self)
        self._multi_exec_dock.setWidget(self._multi_exec_panel)
        self._multi_exec_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self._multi_exec_dock.setVisible(False)
        self._multi_exec_dock.visibilityChanged.connect(self._on_multi_exec_visibility)
        self.addDockWidget(Qt.RightDockWidgetArea, self._multi_exec_dock)

        # Wire MultiExecPanel signals
        self._multi_exec_panel.broadcast_requested.connect(self._on_broadcast_requested)

        # Poll for tab changes to refresh the panel
        self._multi_exec_timer = QTimer(self)
        self._multi_exec_timer.timeout.connect(self._refresh_multi_exec_panel)
        self._multi_exec_timer.start(1000)

    # ── MultiExec / broadcast ────────────────────────────────────────────────

    def _toggle_multi_exec_panel(self) -> None:
        """Toggle the MultiExec dock panel visibility."""
        visible = self._multi_exec_dock.isVisible()
        self._multi_exec_dock.setVisible(not visible)
        if not visible:
            self._refresh_multi_exec_panel()

    def _on_multi_exec_visibility(self, visible: bool) -> None:
        """Sync toolbar button state with dock visibility."""
        self.multi_exec_btn.setChecked(visible)
        if not visible:
            self._disconnect_broadcast()

    def _refresh_multi_exec_panel(self) -> None:
        """Refresh the panel with current SSH tabs from all workspaces."""
        workspaces = self.workspace_container.get_all_workspaces()
        all_tabs: list = []
        for ws in workspaces:
            all_tabs.extend(ws.all_ssh_tabs())
        self._multi_exec_panel.refresh_tabs(all_tabs)

    def _on_broadcast_requested(self, enabled: bool) -> None:
        """Handle broadcast state change from the MultiExec panel."""
        if enabled:
            tabs = self._multi_exec_panel.selected_tabs()
            if not tabs:
                self.broadcast_mode = False
                self.connection_event_area.showMessage(
                    _("MultiExec requires at least one opted-in connected SSH session"),
                    4000,
                )
                return
            self.broadcast_mode = True
            self._connect_broadcast()
            self.connection_event_area.showMessage(
                _("MultiExec active — {} target(s)").format(len(tabs)),
                3000,
            )
        else:
            self.broadcast_mode = False
            self._disconnect_broadcast()
            self.connection_event_area.showMessage(
                _("MultiExec stopped"),
                3000,
            )

    def _connect_broadcast(self) -> None:
        """Wire broadcast: terminal keystrokes go to opted-in sessions only."""
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            tabs = ws.all_ssh_tabs()
            for tab in tabs:
                try:
                    tab.terminal.key_pressed.disconnect(self._broadcast_key)
                except (TypeError, RuntimeError):
                    pass
                tab.terminal.key_pressed.connect(self._broadcast_key)
        self._update_broadcast_indicators()

    def _disconnect_broadcast(self) -> None:
        """Remove broadcast wiring and clear opt-ins."""
        # Disconnect key_pressed from all workspace tabs
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            tabs = ws.all_ssh_tabs()
            for tab in tabs:
                try:
                    tab.terminal.key_pressed.disconnect(self._broadcast_key)
                except (TypeError, RuntimeError):
                    pass
        # Clear opt-ins via the panel (handles tabs not in workspace too)
        self._multi_exec_panel.clear_all()
        self._update_broadcast_indicators()

    def _broadcast_key(self, text: str) -> None:
        """Forward a keystroke to opted-in SSH backends only."""
        if not self.broadcast_mode:
            return
        for tab in self._multi_exec_panel.selected_tabs():
            if tab.backend and tab.backend.is_connected():
                tab.backend.send(text)

    def _update_broadcast_indicators(self) -> None:
        """Update tab labels to show broadcast participation."""
        workspaces = self.workspace_container.get_all_workspaces()
        opted_in_tabs = self._multi_exec_panel.selected_tabs()
        opted_in_ids = {id(t) for t in opted_in_tabs}
        for ws in workspaces:
            for i in range(ws.count()):
                w = ws.widget(i)
                from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab
                if isinstance(w, SshTerminalTab):
                    text = ws.tabText(i)
                    if id(w) in opted_in_ids:
                        if not text.startswith("📢"):
                            ws.setTabText(i, f"📢 {text}")
                    else:
                        if text.startswith("📢 "):
                            ws.setTabText(i, text[3:])

    def _set_workspace_layout(self, layout: str) -> None:
        """Set the workspace layout."""
        self.workspace_layout = layout

        # Update button states
        self.split_single_btn.setChecked(layout == "single")
        self.split_horizontal_btn.setChecked(layout == "horizontal")
        self.split_vertical_btn.setChecked(layout == "vertical")
        self.split_grid_btn.setChecked(layout == "grid")

        # Set the layout in the workspace container
        self.workspace_container.set_layout_mode(layout)

        # Show layout change message
        self.connection_event_area.showMessage(f"Layout: {layout}", 3000)

    def _setup_status_bar(self) -> None:
        """Setup the status bar."""
        self.connection_event_area = ConnectionEventArea()
        self.setStatusBar(self.connection_event_area)
        self.connection_event_area.showMessage("Ready", 0)

    def _setup_menu_bar(self) -> None:
        """Setup the menu bar with Vault menu."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu(_("&File"))

        new_profile_action = QAction(_("New Profile..."), self)
        new_profile_action.triggered.connect(self._new_profile)
        file_menu.addAction(new_profile_action)

        new_local_action = QAction(_("💻 New Local Terminal"), self)
        new_local_action.triggered.connect(self._new_local_terminal)
        file_menu.addAction(new_local_action)

        file_menu.addSeparator()

        import_action = QAction(_("Import from MobaXterm..."), self)
        import_action.triggered.connect(self._import_mobaxterm)
        file_menu.addAction(import_action)

        putty_action = QAction(_("Import from PuTTY (.reg)..."), self)
        putty_action.triggered.connect(self._import_putty)
        file_menu.addAction(putty_action)

        file_menu.addSeparator()

        export_json_action = QAction(_("Export Sessions (JSON)..."), self)
        export_json_action.triggered.connect(self._export_sessions_json)
        file_menu.addAction(export_json_action)

        import_json_action = QAction(_("Import Sessions (JSON)..."), self)
        import_json_action.triggered.connect(self._import_sessions_json)
        file_menu.addAction(import_json_action)

        file_menu.addSeparator()

        exit_action = QAction(_("Exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Vault menu
        vault_menu = menu_bar.addMenu(_("&Vault"))

        self.setup_vault_action = QAction(_("Setup Master Password..."), self)
        self.setup_vault_action.triggered.connect(self._setup_vault)
        vault_menu.addAction(self.setup_vault_action)

        self.unlock_vault_action = QAction(_("Unlock Vault..."), self)
        self.unlock_vault_action.triggered.connect(self._unlock_vault)
        vault_menu.addAction(self.unlock_vault_action)

        self.lock_vault_action = QAction(_("Lock Vault"), self)
        self.lock_vault_action.triggered.connect(self._lock_vault)
        self.lock_vault_action.setEnabled(False)
        vault_menu.addAction(self.lock_vault_action)

        self.upgrade_vault_action = QAction(_("Upgrade Vault Security…"), self)
        self.upgrade_vault_action.triggered.connect(self._on_upgrade_vault)
        vault_menu.addAction(self.upgrade_vault_action)

        vault_menu.addSeparator()

        manage_accounts_action = QAction(_("Manage Accounts..."), self)
        manage_accounts_action.triggered.connect(self._manage_accounts)
        vault_menu.addAction(manage_accounts_action)

        self._update_vault_menu()

        # Tools menu
        tools_menu = menu_bar.addMenu(_("&Tools"))

        tunnels_action = QAction(_("Tunnels..."), self)
        tunnels_action.triggered.connect(self._show_tunnel_manager)
        tools_menu.addAction(tunnels_action)

        tools_menu.addSeparator()

        launch_gui_action = QAction(_("Launch Remote GUI App..."), self)
        launch_gui_action.triggered.connect(self._show_gui_launcher)
        tools_menu.addAction(launch_gui_action)

        tools_menu.addSeparator()

        snippets_action = QAction(_("Manage Snippets..."), self)
        snippets_action.triggered.connect(self._show_snippet_manager)
        tools_menu.addAction(snippets_action)

        # Sync menu
        sync_menu = menu_bar.addMenu(_("&Sync"))

        self.sync_settings_action = QAction(_("⚙ Sync Settings..."), self)
        self.sync_settings_action.triggered.connect(self._show_sync_settings)
        sync_menu.addAction(self.sync_settings_action)

        self.sync_now_action = QAction(_("🔄 Sync Now"), self)
        self.sync_now_action.triggered.connect(self._sync_now)
        self.sync_now_action.setEnabled(self.sync_manager.config.enabled)
        sync_menu.addAction(self.sync_now_action)

        sync_menu.addSeparator()

        self.sync_push_action = QAction(_("⬆ Push to Cloud"), self)
        self.sync_push_action.triggered.connect(self._sync_push)
        self.sync_push_action.setEnabled(self.sync_manager.config.enabled)
        sync_menu.addAction(self.sync_push_action)

        self.sync_pull_action = QAction(_("⬇ Pull from Cloud"), self)
        self.sync_pull_action.triggered.connect(self._sync_pull)
        self.sync_pull_action.setEnabled(self.sync_manager.config.enabled)
        sync_menu.addAction(self.sync_pull_action)

        file_menu.addSeparator()

        settings_action = QAction(_("⚙ Settings..."), self)
        settings_action.triggered.connect(self._show_settings_dialog)
        file_menu.addAction(settings_action)

        # Language menu
        self._setup_language_menu(menu_bar)

    def _update_vault_menu(self) -> None:
        """Update vault menu items based on vault state."""
        unlocked = self.vault_manager.is_unlocked()
        self.unlock_vault_action.setEnabled(not unlocked)
        self.lock_vault_action.setEnabled(unlocked)

    def _on_upgrade_vault(self) -> None:
        """Handle vault upgrade action from menu."""
        try:
            ver = inspect_vault_version(Path(self.vault_manager.vault_path))
        except VaultUpgradeError as e:
            QMessageBox.critical(self, "Vault Upgrade", f"Could not read vault file:\n{str(e)}")
            return

        if ver == 2:
            QMessageBox.information(self, "Vault Upgrade", "Already using v2.")
            return

        # Show warning dialog for v1 upgrade
        reply = QMessageBox.warning(
            self, "Vault Upgrade",
            "This will upgrade to v2. A backup will be created. Only proceed if no other instance is using this vault.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Check if vault is unlocked and ask for re-locking
        if self.vault_manager.is_unlocked():
            reply = QMessageBox.question(
                self, "Vault Upgrade",
                "Vault will be locked before upgrade. You will need to re-enter your master password. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # Lock the vault
            self.vault_manager.lock()
            self._last_vault_unlocked = False
            self._update_vault_menu()

        # Get password
        password, ok = QInputDialog.getText(
            self, "Vault Upgrade",
            "Enter master password:",
            QLineEdit.Password
        )
        if not ok or not password:
            # If vault was locked, it stays locked
            return

        # Perform upgrade
        try:
            result = upgrade_vault_v1_to_v2(Path(self.vault_manager.vault_path), password)
        except VaultUpgradeError as e:
            self._show_upgrade_error(e)
            return

        # Show result
        if result.backup_deleted:
            QMessageBox.information(self, "Vault Upgrade", "Upgraded to v2. Backup removed.")
        else:
            QMessageBox.warning(self, "Vault Upgrade", f"Upgraded to v2.\nBackup retained: {result.retained_backup_path}")

    def _show_upgrade_error(self, error: VaultUpgradeError) -> None:
        """Show appropriate error message for vault upgrade failure."""
        if error.rollback_succeeded is None:
            # Critical error: source was not replaced
            msg = f"{str(error)}\n\nSource was not replaced."
        elif error.rollback_succeeded is True:
            # Warning: original v1 restored
            msg = "Original v1 restored."
        elif error.rollback_succeeded is False:
            # Critical error: rollback failed
            msg = "Rollback failed."
        else:
            # Should not happen, but just in case
            msg = str(error)

        if error.recovery_backup_path:
            msg += f"\nRecovery: {error.recovery_backup_path}"

        if error.rollback_succeeded is True:
            QMessageBox.warning(self, "Vault Upgrade", msg)
        else:
            QMessageBox.critical(self, "Vault Upgrade", msg)

    def _poll_vault_lock_state(self) -> None:
        """Periodic check for vault auto-lock transitions."""
        unlocked = self.vault_manager.is_unlocked()
        if self._last_vault_unlocked and not unlocked:
            # Transition unlocked → locked (auto-lock)
            self.connection_event_area.showMessage("Vault auto-locked", 5000)
        self._update_vault_menu()
        self._last_vault_unlocked = unlocked

    def _setup_vault(self) -> None:
        """Setup master password for vault."""
        if self.vault_manager.is_unlocked():
            QMessageBox.information(self, "Vault",
                "Vault is already set up and unlocked.")
            return

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
            self._last_vault_unlocked = self.vault_manager.is_unlocked()
            QMessageBox.information(self, "Success",
                "Master password set. Unlock the vault to add accounts.")
            self.connection_event_area.showMessage("Vault created", 3000)
        else:
            QMessageBox.critical(self, "Error", "Failed to set up vault.")
        self._update_vault_menu()

    def _unlock_vault(self) -> None:
        """Unlock vault with master password."""
        if not self.vault_manager.is_unlocked():
            # Check if vault file exists before prompting for password
            if not os.path.exists(self.vault_manager.vault_path):
                reply = QMessageBox.question(
                    self, "No Vault",
                    "No vault found. Set up a master password first?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    self._setup_vault()
                return

            password, ok = QInputDialog.getText(
                self, "Unlock Vault",
                "Enter master password:",
                QLineEdit.Password
            )
            if ok and password:
                if self.vault_manager.unlock(password):
                    self._last_vault_unlocked = True
                    self.connection_event_area.showMessage("Vault unlocked", 3000)
                    self._update_vault_menu()
                else:
                    QMessageBox.critical(self, "Error",
                        "Wrong password.")

    def _lock_vault(self) -> None:
        """Lock the vault."""
        self.vault_manager.lock()
        self._last_vault_unlocked = False
        self.connection_event_area.showMessage("Vault locked", 3000)
        self._update_vault_menu()

    def _manage_accounts(self) -> None:
        """Open the Account Manager dialog."""
        # First ensure vault is unlocked
        if not self.vault_manager.is_unlocked():
            ret = QMessageBox.question(
                self, "Vault Locked",
                "Vault is locked. Would you like to unlock it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self._unlock_vault()
                if not self.vault_manager.is_unlocked():
                    return  # Still locked
            else:
                return

        dialog = QDialog(self)
        dialog.setWindowTitle("Account Manager - Vault")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        account_manager = AccountManager(self.vault_manager)
        layout.addWidget(account_manager)
        dialog.exec()

    def _new_profile(self) -> None:
        """Create a new profile using the Session Wizard."""
        from openadmindesk.ui.session_wizard import SessionWizard
        wiz = SessionWizard(self.profile_store, self.vault_manager, self)
        if wiz.exec() == wiz.Accepted:
            profile = wiz.profile()
            if profile and wiz.connect_after():
                self._open_ssh_tab(profile)
            self.connection_tree.refresh()

    def _new_local_terminal(self) -> None:
        """Open a local shell terminal tab."""
        from openadmindesk.ui.local_shell_tab import LocalShellTab
        tab = LocalShellTab()
        self.tab_widget.addTab(tab, _("💻 Local Shell"))
        self.tab_widget.setCurrentWidget(tab)
        self.connection_event_area.showMessage("Local terminal opened", 3000)

    def _import_mobaxterm(self) -> None:
        """Import sessions from a MobaXterm.ini file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import MobaXterm Configuration",
            "",
            "MobaXterm Config (MobaXterm.ini);;All Files (*)"
        )
        if not path:
            return

        from openadmindesk.core.mobaxterm_importer import MobaXtermImporter
        importer = MobaXtermImporter(self.profile_store)
        imported, skipped = importer.import_file(path)

        self.connection_tree.refresh()
        self.connection_event_area.showMessage(
            f"Imported {imported} sessions from MobaXterm"
            + (f" ({skipped} skipped)" if skipped else ""),
            8000
        )
        QMessageBox.information(
            self, "Import Complete",
            f"Imported {imported} sessions into 'Imported from MobaXterm' folder.\n"
            + (f"{skipped} entries skipped (WSL, local terminal, etc.)"
               if skipped else "")
        )

    def _import_putty(self) -> None:
        """Import sessions from a PuTTY .reg file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PuTTY Sessions", "",
            "Registry Files (*.reg);;All Files (*)"
        )
        if not path:
            return
        from openadmindesk.core.putty_importer import PuttyImporter
        importer = PuttyImporter(self.profile_store)
        imported, skipped = importer.import_file(path)
        self.connection_tree.refresh()
        msg = f"Imported {imported} sessions from PuTTY"
        if skipped:
            msg += f" ({skipped} skipped)"
        self.connection_event_area.showMessage(msg, 5000)

    def _export_sessions_json(self) -> None:
        """Export all sessions to a JSON file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Sessions", "openadmindesk_sessions.json",
            "JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        from openadmindesk.core.profile_import_export import ProfileExporter
        profiles = self.profile_store.load_all_profiles()
        if ProfileExporter.export_to_json(profiles, path):
            self.connection_event_area.showMessage(
                f"Exported {len(profiles)} sessions to JSON", 5000
            )
        else:
            QMessageBox.critical(self, "Error", "Export failed.")

    def _import_sessions_json(self) -> None:
        """Import sessions from a JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Sessions", "",
            "JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        from openadmindesk.core.profile_import_export import ProfileImporter
        imported = ProfileImporter.import_from_json(path)
        for profile in imported:
            profile.parent_folder = "Imported"
            self.profile_store.save_profile(profile)
        self.connection_tree.refresh()
        self.connection_event_area.showMessage(
            f"Imported {len(imported)} sessions from JSON", 5000
        )

    # ── sync ──────────────────────────────────────────────────────────────────

    def _show_sync_settings(self) -> None:
        from openadmindesk.ui.sync_settings import SyncSettingsDialog
        dlg = SyncSettingsDialog(self.sync_manager, self)
        if dlg.exec() == SyncSettingsDialog.Accepted:
            self._update_sync_menu()
            self.connection_event_area.showMessage("Sync settings updated", 3000)

    def _sync_now(self) -> None:
        self._prompt_sync_password(lambda pwd: self._do_sync(pwd, "auto"))

    def _sync_push(self) -> None:
        self._prompt_sync_password(lambda pwd: self._do_sync(pwd, "push"))

    def _sync_pull(self) -> None:
        self._prompt_sync_password(lambda pwd: self._do_sync(pwd, "pull"))

    def _prompt_sync_password(self, callback) -> None:
        pwd, ok = QInputDialog.getText(
            self, "Sync Password",
            "Enter sync encryption password:",
            QLineEdit.Password,
        )
        if ok and pwd:
            callback(pwd)

    def _do_sync(self, password: str, action: str) -> None:
        if not self.sync_manager.config.sync_folder:
            QMessageBox.warning(self, "Sync", "Configure sync folder first (Sync → Settings).")
            return

        if action == "auto":
            msg = self.sync_manager.auto_sync(password)
        elif action == "push":
            ok = self.sync_manager.push(password)
            msg = "✅ Pushed to cloud." if ok else "❌ Push failed."
        elif action == "pull":
            msg = self.sync_manager.pull(password)
        else:
            return

        if msg:
            self.connection_tree.refresh()
            self.connection_event_area.showMessage(msg, 5000)
            self._update_sync_menu()

    def _update_sync_menu(self) -> None:
        enabled = self.sync_manager.config.enabled
        self.sync_now_action.setEnabled(enabled)
        self.sync_push_action.setEnabled(enabled)
        self.sync_pull_action.setEnabled(enabled)

    # ── language ──────────────────────────────────────────────────────────────

    def _setup_language_menu(self, menu_bar) -> None:
        from openadmindesk.core.l10n import available_languages, current_language
        lang_menu = menu_bar.addMenu(_("&Language"))
        langs = available_languages()
        for code, name in langs.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(code == current_language())
            action.triggered.connect(lambda checked, c=code: self._switch_language(c))
            lang_menu.addAction(action)

    def _switch_language(self, code: str) -> None:
        from openadmindesk.core.l10n import load_language
        if load_language(code):
            self.connection_event_area.showMessage(
                f"Language: {code}", 3000
            )
            self.menuBar().clear()
            self._setup_menu_bar()
            self._update_vault_menu()

    def _show_settings_dialog(self) -> None:
        """Open the central settings dialog."""
        from openadmindesk.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._settings_store, self._app_settings, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._app_settings = dlg.result_settings()
            self._apply_app_settings()
            self.connection_event_area.showMessage(
                _("Settings saved"), 3000
            )

    def _apply_app_settings(self) -> None:
        """Apply saved settings to already-open widgets where possible."""
        for workspace in self.workspace_container.get_all_workspaces():
            for tab in workspace.all_ssh_tabs():
                self._apply_terminal_settings(tab)

    def _apply_terminal_settings(self, tab) -> None:
        tab.terminal.set_font(
            self._app_settings.terminal_font_family,
            self._app_settings.terminal_font_size,
        )
        tab.terminal.set_bg_opacity(self._app_settings.terminal_bg_opacity)
        tab.terminal._max_scrollback = self._app_settings.terminal_scrollback_lines

    def _on_new_session_requested(self, session_type: SessionType, parent_folder: Optional[str]) -> None:
        """Handle new session request from connection tree context menu."""
        default_host = ""
        default_port = 22 if session_type == SessionType.SSH else 3389
        profile = Profile(
            name="New Session",
            host=default_host,
            port=default_port,
            session_type=session_type,
            parent_folder=parent_folder,
        )
        self._open_profile_editor(profile)

    def _open_profile_editor(self, profile: Profile) -> None:
        """Open profile editor for the given profile and refresh tree on save."""
        editor = ProfileEditor(profile, self.profile_store, self.vault_manager)
        editor.profile_saved.connect(
            lambda name: self._on_profile_saved(name)
        )
        editor.setWindowModality(Qt.ApplicationModal)
        editor.setAttribute(Qt.WA_DeleteOnClose, False)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        # Keep reference to prevent garbage collection
        if not hasattr(self, '_open_editors'):
            self._open_editors = []
        self._open_editors.append(editor)
        # Clean up closed editors from list periodically
        self._open_editors = [e for e in self._open_editors if e.isVisible()]

    def _on_profile_edit_requested(self, profile_name: str) -> None:
        """Handle profile edit request from connection tree."""
        profile = self.profile_store.load_profile(profile_name)
        if profile:
            self._open_profile_editor(profile)
        else:
            QMessageBox.warning(self, "Error",
                f"Profile '{profile_name}' not found.")

    def _show_tunnel_manager(self) -> None:
        """Open the tunnel manager dialog."""
        from PySide6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Tunnel Manager")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        tunnel_widget = TunnelManagerWidget(dialog)
        tunnel_widget.status_message.connect(
            lambda msg: self.connection_event_area.showMessage(msg, 5000)
        )
        layout.addWidget(tunnel_widget)
        dialog.exec()

    def _show_gui_launcher(self) -> None:
        """Open the GUI launcher dialog."""
        # Reuse the tunnel manager's launch functionality
        from openadmindesk.ui.tunnel_manager import TunnelManagerWidget
        # Create a temporary widget just for the launch dialog
        temp = TunnelManagerWidget()
        temp._launch_gui_app()

    def _show_snippet_manager(self) -> None:
        """Open the snippet manager dialog."""
        from PySide6.QtWidgets import QDialog

        dialog = QDialog(self)
        dialog.setWindowTitle("Snippet Manager")
        dialog.setMinimumSize(550, 400)
        layout = QVBoxLayout(dialog)
        snippet_widget = SnippetManagerWidget(parent=dialog)
        snippet_widget.snippet_insert_requested.connect(
            lambda sid, sname: self.connection_event_area.showMessage(
                f"Snippet '{sname}' ready — open an SSH tab to insert", 5000
            )
        )
        layout.addWidget(snippet_widget)
        dialog.exec()

    def _on_profile_delete_requested(self, profile_name: str) -> None:
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Are you sure you want to delete profile '{profile_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.profile_store.delete_profile(profile_name)
            self.connection_tree.refresh()
            self.connection_event_area.showMessage(f"Profile '{profile_name}' deleted", 3000)

    def _on_profile_duplicate_requested(self, profile_name: str) -> None:
        original = self.profile_store.load_profile(profile_name)
        if not original:
            return
        new_name = f"{profile_name} (copy)"
        import copy
        new_profile = copy.deepcopy(original)
        new_profile.name = new_name
        # Strip vault reference so the copy gets its own credentials
        new_profile.credential_id = None
        new_profile.rdp_gateway_credential_id = None
        self.profile_store.save_profile(new_profile)
        self.connection_tree.refresh()
        self.connection_event_area.showMessage(f"Duplicated to '{new_name}'", 3000)

    def _on_profile_export_requested(self, profile_name: str) -> None:
        """Export a single profile to a JSON file."""
        export_path, _filter = QFileDialog.getSaveFileName(
            self, _("Export Profile"), f"{profile_name}.json",
            _("JSON (*.json);;All Files (*)")
        )
        if not export_path:
            return
        profile = self.profile_store.load_profile(profile_name)
        if not profile:
            return
        from openadmindesk.core.profile_import_export import ProfileExporter
        if ProfileExporter.export_to_json([profile], export_path):
            self.connection_event_area.showMessage(
                f"Exported '{profile_name}'", 3000
            )
        else:
            QMessageBox.critical(self, "Error", _("Export failed."))

    def _on_profile_sftp_requested(self, profile_name: str) -> None:
        """Open a dedicated SFTP tab for the given profile."""
        profile = self.profile_store.load_profile(profile_name)
        if not profile:
            return
        profile = self._profile_with_vault_credentials(profile)
        active_workspace = self.workspace_container.get_active_workspace()
        from openadmindesk.ui.sftp_file_browser import SftpFileBrowser
        browser = SftpFileBrowser(profile)
        tab_name = f"📁 {profile.name} (SFTP)"
        active_workspace.addTab(browser, tab_name)
        active_workspace.setCurrentWidget(browser)

    def _on_folder_launch_requested(self, folder_name: str) -> None:
        """Open all sessions in a folder."""
        profiles = self.profile_store.load_all_profiles()
        folder_profiles = [p for p in profiles if p.parent_folder == folder_name]
        for profile in folder_profiles:
            self._open_ssh_tab(profile)
        count = len(folder_profiles)
        if count == 0:
            self.connection_event_area.showMessage(
                f"Folder '{folder_name}' is empty", 3000
            )
        else:
            self.connection_event_area.showMessage(
                f"Launched {count} session(s) from '{folder_name}'", 4000
            )

    def _on_quick_connect(self, host: str) -> None:
        """Handle quick connect with credentials dialog."""
        # Parse user@host:port format
        username = ""
        port = 22

        if '@' in host:
            parts = host.split('@', 1)
            username = parts[0]
            host = parts[1]

        if ':' in host:
            parts = host.split(':', 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                port = 22

        # Show quick credentials dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Quick Connect")
        dlg.setMinimumWidth(350)
        form = QFormLayout(dlg)

        host_input = QLineEdit(host)
        form.addRow(_("Host:"), host_input)

        user_input = QLineEdit(username)
        user_input.setPlaceholderText("root")
        form.addRow(_("Username:"), user_input)

        port_input = QSpinBox()
        port_input.setRange(1, 65535)
        port_input.setValue(port)
        form.addRow(_("Port:"), port_input)

        pass_input = QLineEdit()
        pass_input.setEchoMode(QLineEdit.Password)
        form.addRow(_("Password:"), pass_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        profile = Profile(
            name=f"quick-{host_input.text().strip()}",
            host=host_input.text().strip(),
            port=port_input.value(),
            username=user_input.text().strip() or "root",
            password=pass_input.text() or None,
        )

        self._open_ssh_tab(profile)
        self.connection_event_area.showMessage(
            f"Connecting to {profile.username}@{profile.host}:{profile.port}...", 5000
        )

    def _on_profile_saved(self, profile_name: str) -> None:
        """Handle profile saved event."""
        self.connection_tree.refresh()
        self.connection_event_area.showMessage(
            f"Profile '{profile_name}' saved", 3000
        )

    def _profile_with_vault_credentials(self, profile: Profile) -> Profile:
        if not self.vault_manager.is_unlocked():
            return profile

        runtime_profile = copy.deepcopy(profile)
        if profile.credential_id:
            account = self.vault_manager.get_account(profile.credential_id)
            if account:
                if account.username and not runtime_profile.username:
                    runtime_profile.username = account.username
                runtime_profile.password = account.password
                runtime_profile.private_key_passphrase = account.private_key_passphrase

        if profile.rdp_gateway_credential_id:
            gateway_account = self.vault_manager.get_account(profile.rdp_gateway_credential_id)
            if gateway_account:
                if gateway_account.host and not runtime_profile.rdp_gateway:
                    runtime_profile.rdp_gateway = gateway_account.host
                if gateway_account.username and not runtime_profile.rdp_gateway_username:
                    runtime_profile.rdp_gateway_username = gateway_account.username
                runtime_profile.rdp_gateway_password = gateway_account.password

        return runtime_profile

    def _open_ssh_tab(self, profile: Profile) -> None:
        """Open a session tab for the given profile and auto-connect."""
        profile = self._profile_with_vault_credentials(profile)
        tab_name = f"{profile.icon} {profile.name}"

        # Check if session already exists in any workspace
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            for i in range(ws.count()):
                if ws.tabText(i) == tab_name:
                    ws.setCurrentIndex(i)
                    return

        # Get the active workspace to open the new session
        active_workspace = self.workspace_container.get_active_workspace()

        if profile.session_type == SessionType.RDP:
            from openadmindesk.ui.rdp_session_tab import RdpSessionTab
            tab = RdpSessionTab(profile)
            active_workspace.addTab(tab, tab_name)
        elif profile.session_type == SessionType.TELNET:
            from openadmindesk.ui.telnet_session_tab import TelnetSessionTab
            tab = TelnetSessionTab(profile)
            active_workspace.addTab(tab, tab_name)
        elif profile.session_type == SessionType.VNC:
            from openadmindesk.ui.vnc_session_tab import VncSessionTab
            tab = VncSessionTab(profile)
            active_workspace.addTab(tab, tab_name)
        elif profile.session_type == SessionType.LOCAL_SHELL:
            from openadmindesk.ui.local_shell_tab import LocalShellTab
            tab = LocalShellTab(profile.name or "Local Shell")
            active_workspace.addTab(tab, tab_name)
            active_workspace.setCurrentWidget(tab)
        else:
            active_workspace.add_ssh_terminal_tab(profile)
            from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab
            current_tab = active_workspace.currentWidget()
            if isinstance(current_tab, SshTerminalTab):
                self._apply_terminal_settings(current_tab)
        # Auto-connect: click the Connect button if present
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._auto_connect_tab(tab_name))

        self.connection_event_area.showMessage(
            f"Opening {profile.session_type.value.upper()} to {profile.host}...", 3000
        )
        # Wire broadcast
        if self.broadcast_mode:
            self._connect_broadcast()
        self._update_status_bar_sessions()

    def _auto_connect_tab(self, tab_name: str) -> None:
        """Auto-click the Connect button on a newly opened session tab."""
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            for i in range(ws.count()):
                if ws.tabText(i).endswith(tab_name.split(" ", 1)[-1]) or \
                   tab_name in ws.tabText(i):
                    w = ws.widget(i)
                    if hasattr(w, '_connect') and hasattr(w, '_connected') and not w._connected:
                        w._connect()
                        return

    def _update_status_bar_sessions(self) -> None:
        """Update the status bar session counter."""
        workspaces = self.workspace_container.get_all_workspaces()
        total = 0
        connected = 0

        for ws in workspaces:
            total += ws.count()
            from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab
            for i in range(ws.count()):
                w = ws.widget(i)
                if isinstance(w, SshTerminalTab) and w._connected:
                    connected += 1

        self.connection_event_area.update_session_count(connected, total)

    def _on_activity_mode_changed(self, mode: str) -> None:
        """Handle activity rail mode changes."""
        self.connection_event_area.showMessage(f"Mode: {mode}", 3000)

    def closeEvent(self, event) -> None:
        """Handle window closing."""
        # Close detached windows from all workspaces
        workspaces = self.workspace_container.get_all_workspaces()
        for ws in workspaces:
            ws.cleanup_detached()

        # Close all tabs from all workspaces
        for ws in workspaces:
            while ws.count() > 0:
                widget = ws.widget(0)
                if hasattr(widget, 'close'):
                    widget.close()
                ws.removeTab(0)

        # Shutdown core services
        self.profile_store.close()
        self.vault_manager.close()
        self.sync_manager.close()

        event.accept()


def create_main_window() -> MainWindow:
    """Create and return the main application window."""
    return MainWindow()
