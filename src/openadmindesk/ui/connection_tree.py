"""Connection tree widget — sessions with folders, drag-and-drop, and search filter."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QInputDialog,
    QMessageBox,
    QAbstractItemView,
    QLineEdit,
)
from PySide6.QtCore import QSize
try:
    from PySide6.QtGui import QAction  # PySide6 >= 6.11  # noqa: F401
except ImportError:
    pass  # PySide6 < 6.11 — QAction was in QtWidgets
from PySide6.QtCore import Qt, Signal
from typing import Optional, Callable

from openadmindesk.core.profile_store import ProfileStore, Folder
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.l10n import _
from openadmindesk.ui.session_icons import (
    default_icon_id_for_session_type,
    session_icon,
)

ROLE_PROFILE = Qt.UserRole
ROLE_FOLDER = Qt.UserRole + 1
ROLE_IS_FOLDER = Qt.UserRole + 2


class ConnectionTree(QWidget):
    """Session tree container with search filter and drag-and-drop support.

    Wraps an internal QTreeWidget and exposes the same signals.
    """

    connection_requested = Signal(object)
    profile_edit_requested = Signal(str)
    profile_delete_requested = Signal(str)
    profile_duplicate_requested = Signal(str)
    profile_export_requested = Signal(str)
    profile_sftp_requested = Signal(str)
    folder_launch_requested = Signal(str)  # folder name
    tree_changed = Signal()
    new_profile_requested: Optional[Callable] = None

    def __init__(self, store: Optional[ProfileStore] = None) -> None:
        super().__init__()
        self.store = store or ProfileStore()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search filter
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(_("Filter sessions..."))
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_input)
        
        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)  # Hide header for compact look
        self._tree.setDragDropMode(QAbstractItemView.InternalMove)
        self._tree.setDefaultDropAction(Qt.MoveAction)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.model().rowsInserted.connect(lambda *a: self._on_tree_reordered())
        self._tree.model().rowsRemoved.connect(lambda *a: self._on_tree_reordered())
        
        # Compact tree settings
        self._tree.setIndentation(12)  # Smaller indentation
        self._tree.setIconSize(QSize(16, 16))  # Smaller icons
        
        layout.addWidget(self._tree)
        self.refresh()

    # ── tree building ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._tree.clear()
        profiles = self.store.load_all_profiles()
        folders = self.store.load_all_folders()

        # Build folder tree
        folder_items: dict[str, QTreeWidgetItem] = {}
        for folder in folders:
            parent_item = folder_items.get(folder.parent) if folder.parent else None
            item = self._build_folder_item(folder.name)
            if parent_item:
                parent_item.addChild(item)
            else:
                self._tree.addTopLevelItem(item)
            folder_items[folder.name] = item

        # Place profiles in folders
        unplaced_profiles = []
        for profile in profiles:
            if profile.parent_folder and profile.parent_folder in folder_items:
                folder_items[profile.parent_folder].addChild(
                    self._build_profile_item(profile)
                )
            else:
                unplaced_profiles.append(profile)

        # Ungrouped profiles at root level
        ssh_unplaced = [p for p in unplaced_profiles if p.session_type == SessionType.SSH]
        rdp_unplaced = [p for p in unplaced_profiles if p.session_type == SessionType.RDP]
        telnet_unplaced = [p for p in unplaced_profiles if p.session_type == SessionType.TELNET]

        if ssh_unplaced:
            ssh_root = self._build_folder_item(
                _("SSH Sessions") + f"  ({len(ssh_unplaced)})",
                "ssh",
            )
            ssh_root.setData(0, ROLE_IS_FOLDER, False)
            self._tree.addTopLevelItem(ssh_root)
            for p in ssh_unplaced:
                ssh_root.addChild(self._build_profile_item(p))

        if telnet_unplaced:
            telnet_root = self._build_folder_item(
                _("Telnet Sessions") + f"  ({len(telnet_unplaced)})",
                "telnet",
            )
            telnet_root.setData(0, ROLE_IS_FOLDER, False)
            self._tree.addTopLevelItem(telnet_root)
            for p in telnet_unplaced:
                telnet_root.addChild(self._build_profile_item(p))

        if rdp_unplaced:
            rdp_root = self._build_folder_item(
                _("RDP Sessions") + f"  ({len(rdp_unplaced)})",
                "rdp",
            )
            rdp_root.setData(0, ROLE_IS_FOLDER, False)
            self._tree.addTopLevelItem(rdp_root)
            for p in rdp_unplaced:
                rdp_root.addChild(self._build_profile_item(p))

        if not profiles and not folders:
            hint = QTreeWidgetItem([_("No sessions yet — right-click → New SSH/RDP or File → New Profile")])
            hint.setFlags(hint.flags() & ~Qt.ItemIsSelectable)
            self._tree.addTopLevelItem(hint)

        self._tree.expandAll()
        self._apply_filter(self.filter_input.text())

    def _build_profile_item(self, profile: Profile) -> QTreeWidgetItem:
        star = "★ " if profile.favorite else ""
        name_text = f"{star}{profile.name}"
        item = QTreeWidgetItem([name_text])
        item.setIcon(
            0,
            session_icon(
                profile.icon_id or default_icon_id_for_session_type(profile.session_type),
                profile.session_type,
            ),
        )
        item.setData(0, ROLE_PROFILE, profile)
        tooltip = profile.description
        if profile.notes:
            tooltip += "\n" + profile.notes
        if profile.tags:
            tooltip += "\nTags: " + profile.tags
        if profile.last_connected:
            tooltip += "\nLast connected: " + profile.last_connected
        if profile.last_error:
            tooltip += "\nLast error: " + profile.last_error
        item.setToolTip(0, tooltip)
        item.setFlags(item.flags() | Qt.ItemIsDragEnabled)
        return item

    def _build_folder_item(self, name: str, icon_id: str = "server") -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setIcon(0, session_icon(icon_id))
        item.setData(0, ROLE_FOLDER, name)
        item.setData(0, ROLE_IS_FOLDER, True)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(item.flags() | Qt.ItemIsDropEnabled)
        return item

    # ── filter ────────────────────────────────────────────────────────────────

    def _apply_filter(self, text: str) -> None:
        """Show/hide items based on filter text.

        Searches profile name, host, username, notes, tags, and protocol type.
        Supports special prefixes:
          tag:mytag  — filter by tag
          proto:ssh  — filter by protocol type
        """
        raw = text.strip()
        text_lower = raw.lower()
        for i in range(self._tree.topLevelItemCount()):
            self._filter_item(self._tree.topLevelItem(i), text_lower)

    def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
        """Recursively filter items. Returns True if item or any child matches."""
        has_match = False

        # Check this item
        if text:
            item_text = item.text(0).lower()
            profile = item.data(0, ROLE_PROFILE)
            if profile and isinstance(profile, Profile):
                # Search in name, host, username, notes
                if (text in item_text
                        or text in profile.host.lower()
                        or text in profile.username.lower()
                        or text in profile.notes.lower()):
                    has_match = True
                # Search in tags
                if not has_match and profile.tags:
                    for tag in profile.tag_list:
                        if text in tag.lower():
                            has_match = True
                            break
                # Search by protocol prefix
                if not has_match and text.startswith("proto:"):
                    proto_filter = text[6:].strip()
                    if proto_filter and proto_filter == profile.session_type.value.lower():
                        has_match = True
                # Search by tag prefix
                if not has_match and text.startswith("tag:"):
                    tag_filter = text[4:].strip()
                    if tag_filter and tag_filter in [t.lower() for t in profile.tag_list]:
                        has_match = True
            elif text in item_text:
                has_match = True
        else:
            has_match = True  # No filter — show all

        # Check children
        child_match = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), text):
                child_match = True

        if child_match:
            has_match = True

        item.setHidden(not has_match)
        # Expand folders that have matching children
        if has_match and item.childCount() > 0 and text:
            self._tree.expandItem(item)

        return has_match

    # ── drag-and-drop persistence ─────────────────────────────────────────────

    def _on_tree_reordered(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            root = self._tree.topLevelItem(i)
            self._persist_item(root, parent_folder=None)
        self.tree_changed.emit()

    def _persist_item(self, item: QTreeWidgetItem, parent_folder: Optional[str]) -> None:
        is_folder = item.data(0, ROLE_IS_FOLDER)
        profile = item.data(0, ROLE_PROFILE)
        if profile and isinstance(profile, Profile):
            if profile.parent_folder != parent_folder:
                self.store.move_profile_to_folder(profile.name, parent_folder)
        if is_folder:
            folder_name = item.data(0, ROLE_FOLDER)
            for i in range(item.childCount()):
                self._persist_item(item.child(i), parent_folder=folder_name)
        elif profile:
            for i in range(item.childCount()):
                self._persist_item(item.child(i), parent_folder=parent_folder)

    # ── interactions ──────────────────────────────────────────────────────────

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        profile = item.data(0, ROLE_PROFILE)
        if profile and isinstance(profile, Profile):
            self.connection_requested.emit(profile)

    def _show_context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        menu = QMenu()
        profile = item.data(0, ROLE_PROFILE) if item else None
        is_folder = item.data(0, ROLE_IS_FOLDER) if item else False

        if is_folder and item.data(0, ROLE_FOLDER):
            parent_folder = item.data(0, ROLE_FOLDER)
        else:
            parent_folder = None

        if profile and isinstance(profile, Profile):
            connect_label = _("Connect")
            if profile.session_type == SessionType.RDP:
                connect_label = _("Connect (RDP)")
            elif profile.session_type == SessionType.TELNET:
                connect_label = _("Connect (Telnet)")
            connect_action = menu.addAction(
                connect_label,
                lambda: self.connection_requested.emit(profile),
            )
            connect_action.setIcon(
                session_icon(
                    profile.icon_id
                    or default_icon_id_for_session_type(profile.session_type),
                    profile.session_type,
                )
            )
            menu.addAction(_("Edit..."), lambda: self.profile_edit_requested.emit(profile.name))
            menu.addAction(_("Duplicate"), lambda: self.profile_duplicate_requested.emit(profile.name))

            # SSH-specific actions
            if profile.session_type == SessionType.SSH:
                sftp_action = menu.addAction(
                    _("Open SFTP"),
                    lambda: self.profile_sftp_requested.emit(profile.name),
                )
                sftp_action.setIcon(session_icon("sftp"))
                ssh_cmd = f"ssh {profile.username}@{profile.host} -p {profile.port}"
                menu.addAction(_("📋 Copy SSH command"),
                               lambda: self._copy_to_clipboard(ssh_cmd))

            menu.addSeparator()
            menu.addAction(_("Export..."), lambda: self.profile_export_requested.emit(profile.name))
            menu.addSeparator()
            menu.addAction(_("Delete"), lambda: self.profile_delete_requested.emit(profile.name))
        elif is_folder and item.data(0, ROLE_FOLDER):
            folder_name = item.data(0, ROLE_FOLDER)
            section = " " + _("in ") + folder_name if folder_name else " " + _("here")
            launch_action = menu.addAction(
                _("Launch all"),
                lambda: self.folder_launch_requested.emit(folder_name),
            )
            launch_action.setIcon(session_icon("server"))
            menu.addSeparator()
            ssh_action = menu.addAction(
                _("New SSH Session") + section,
                lambda: self._request_new_profile(SessionType.SSH, parent_folder),
            )
            ssh_action.setIcon(session_icon("ssh"))
            rdp_action = menu.addAction(
                _("New RDP Session") + section,
                lambda: self._request_new_profile(SessionType.RDP, parent_folder),
            )
            rdp_action.setIcon(session_icon("rdp"))
            menu.addSeparator()
            menu.addAction(_("New Subfolder..."),
                           lambda: self._create_folder(parent=folder_name))
            menu.addSeparator()
            menu.addAction(_("Rename Folder..."), lambda: self._rename_folder(item))
            menu.addAction(_("Delete Folder"), lambda: self._delete_folder(folder_name))
        else:
            ssh_action = menu.addAction(
                _("New SSH Session"),
                lambda: self._request_new_profile(SessionType.SSH, parent_folder),
            )
            ssh_action.setIcon(session_icon("ssh"))
            rdp_action = menu.addAction(
                _("New RDP Session"),
                lambda: self._request_new_profile(SessionType.RDP, parent_folder),
            )
            rdp_action.setIcon(session_icon("rdp"))
            menu.addSeparator()
            menu.addAction(_("New Folder..."), lambda: self._create_folder(parent=None))

        menu.exec(self._tree.mapToGlobal(position))

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)

    def _request_new_profile(self, session_type: SessionType, parent_folder: Optional[str]) -> None:
        if self.new_profile_requested:
            self.new_profile_requested(session_type, parent_folder)

    def _create_folder(self, parent: Optional[str] = None) -> None:
        name, ok = QInputDialog.getText(self, _("New Folder"), _("Folder name:"))
        if ok and name.strip():
            folder = Folder(name=name.strip(), parent=parent)
            self.store.save_folder(folder)
            self.refresh()
            self.tree_changed.emit()

    def _rename_folder(self, item: QTreeWidgetItem) -> None:
        old_name = item.data(0, ROLE_FOLDER)
        new_name, ok = QInputDialog.getText(self, _("Rename Folder"), _("New name:"), text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            self.store.delete_folder(old_name)
            folder = Folder(name=new_name.strip(), parent=None)
            self.store.save_folder(folder)
            self.refresh()
            self.tree_changed.emit()

    def _delete_folder(self, folder_name: str) -> None:
        reply = QMessageBox.question(
            self, _("Delete Folder"),
            _("Delete folder ':folder'?\n\nProfiles inside will be moved to root (not deleted).").replace(":folder", folder_name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.store.delete_folder(folder_name)
            self.refresh()
            self.tree_changed.emit()
