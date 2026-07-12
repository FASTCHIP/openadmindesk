"""Tabbed workspace widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QInputDialog,
    QTabBar,
)
from PySide6.QtCore import Qt
from typing import Optional, List
from openadmindesk.ui.sftp_file_browser import SftpFileBrowser
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab
from openadmindesk.core.profile import Profile
from openadmindesk.core.l10n import _
from openadmindesk.ui.session_icons import (
    default_icon_id_for_session_type,
    session_icon,
)


class TabbedWorkspace(QTabWidget):
    """Tabbed workspace for the main window."""

    def __init__(self) -> None:
        """Initialize the tabbed workspace."""
        super().__init__()
        self.setTabsClosable(False)
        self.setMovable(True)
        self._detached_windows: list[QMainWindow] = []
        self._new_session_callback: Optional[callable] = None

        # Tab context menu
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._tab_context_menu)

        # Tab rename
        self.tabBarDoubleClicked.connect(self._tab_rename)

        # "+" button for new tab
        self._plus_button = QPushButton("+")
        self._plus_button.setFixedSize(28, 22)
        self._plus_button.setStyleSheet(
            "QPushButton { font-size: 16px; font-weight: bold; border: none; "
            "border-radius: 3px; padding: 0; margin: 2; }"
            "QPushButton:hover { background-color: #007acc; }"
        )
        self._plus_button.clicked.connect(self._on_plus_clicked)
        self.setCornerWidget(self._plus_button, Qt.TopRightCorner)

        # Welcome tab
        self._add_welcome_tab()

        # Connect signals
        self.tabCloseRequested.connect(self._close_tab)
        self.currentChanged.connect(self._focus_current_terminal)

    def _add_welcome_tab(self) -> None:
        """Show the initial welcome/info tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignCenter)
        welcome = QLabel(
            "Welcome to OpenAdminDesk\n\n"
            "▸ Create a new profile:  File → New Profile\n"
            "▸ Quick connect:  type user@host in the toolbar\n"
            "▸ Double-click a session in the tree to connect"
        )
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet("color: #969696; font-size: 14px;")
        layout.addWidget(welcome)
        self.addTab(tab, _("Home"))
        
    def add_ssh_terminal_tab(self, profile: Profile) -> None:
        """Add an SSH terminal tab."""
        ssh_tab = SshTerminalTab(profile)
        tab_name = profile.name
        
        index = self.addTab(
            ssh_tab,
            session_icon(
                profile.icon_id or default_icon_id_for_session_type(profile.session_type),
                profile.session_type,
            ),
            tab_name,
        )
        self._install_close_button(index)
        self.setCurrentWidget(ssh_tab)
        self._focus_current_terminal(self.currentIndex())
        
        ssh_tab.connection_status_changed.connect(
            lambda connected: self._on_connection_status_changed(connected, tab_name)
        )
        ssh_tab.tab_closed.connect(
            lambda: self._on_tab_closed(tab_name)
        )
        ssh_tab.sftp_requested.connect(self.add_sftp_browser_tab)

    def add_sftp_browser_tab(self, profile: Profile) -> None:
        """Open SFTP as a dedicated file-browser tab."""
        tab_name = f"SFTP {profile.name}"
        for i in range(self.count()):
            if self.tabText(i) == tab_name:
                self.setCurrentIndex(i)
                return
        browser = SftpFileBrowser(profile)
        index = self.addTab(browser, session_icon("sftp"), tab_name)
        self._install_close_button(index)
        self.setCurrentWidget(browser)
        browser.browser_closed.connect(lambda: self._on_tab_closed(tab_name))

    def _install_close_button(self, index: int) -> None:
        """Install an always-visible close button for a tab."""
        button = QPushButton("x")
        button.setToolTip(_("Close tab"))
        button.setFixedSize(18, 18)
        button.setFocusPolicy(Qt.NoFocus)
        button.setStyleSheet(
            "QPushButton { background: #3c3c3c; color: #d4d4d4; "
            "border: 1px solid #555555; border-radius: 3px; "
            "font-size: 12px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background: #e05555; color: #ffffff; "
            "border-color: #e05555; }"
        )
        button.clicked.connect(lambda: self._close_tab_for_button(button))
        self.tabBar().setTabButton(index, QTabBar.RightSide, button)

    def _close_tab_for_button(self, button: QPushButton) -> None:
        for index in range(self.count()):
            if self.tabBar().tabButton(index, QTabBar.RightSide) is button:
                self._close_tab(index)
                return

    def is_home_tab(self, index: int) -> bool:
        """Return whether a tab is the non-session home tab."""
        return 0 <= index < self.count() and self.tabText(index) == _("Home")

    def extract_content_tabs(self) -> list[tuple[QWidget, object, str]]:
        """Remove and return all non-home tabs while preserving order."""
        tabs: list[tuple[QWidget, object, str]] = []
        index = 0
        while index < self.count():
            if self.is_home_tab(index):
                index += 1
                continue
            widget = self.widget(index)
            icon = self.tabIcon(index)
            title = self.tabText(index)
            self.removeTab(index)
            tabs.append((widget, icon, title))
        return tabs

    def append_existing_tab(self, widget: QWidget, icon, title: str) -> int:
        """Append an already-created tab widget to this workspace."""
        index = self.addTab(widget, icon, title)
        if title != _("Home"):
            self._install_close_button(index)
        return index

    def _focus_current_terminal(self, index: int) -> None:
        """Send keyboard focus into the active terminal tab."""
        if index < 0:
            return
        widget = self.widget(index)
        if isinstance(widget, SshTerminalTab):
            widget.terminal.setFocus(Qt.OtherFocusReason)

    def _on_connection_status_changed(self, connected: bool, tab_name: str) -> None:
        """Update tab name with connection status indicator."""
        for i in range(self.count()):
            if self.tabText(i).startswith(tab_name[:20]):
                status = "●" if connected else "○"
                self.setTabText(i, f"{status} {tab_name}")

    def _on_tab_closed(self, tab_name: str) -> None:
        """Handle tab closed."""
        for i in range(self.count()):
            if self.tabText(i).endswith(tab_name) or tab_name in self.tabText(i):
                self.removeTab(i)
                break

    def _close_tab(self, index: int) -> None:
        """Close a tab."""
        self.removeTab(index)

    # ── detach tabs ───────────────────────────────────────────────────────────

    def _tab_context_menu(self, position) -> None:
        tab_index = self.tabBar().tabAt(position)
        if tab_index < 0:
            return
        try:
            from PySide6.QtGui import QAction
        except ImportError:
            from PySide6.QtWidgets import QAction
        menu = QMenu()
        detach_action = QAction(_("Detach Tab"), self)
        detach_action.triggered.connect(lambda: self._detach_tab(tab_index))
        menu.addAction(detach_action)
        close_action = QAction(_("Close Tab"), self)
        close_action.triggered.connect(lambda: self._close_tab(tab_index))
        menu.addAction(close_action)
        menu.exec(self.tabBar().mapToGlobal(position))

    def _detach_tab(self, index: int) -> None:
        widget = self.widget(index)
        if not widget:
            return
        title = self.tabText(index)
        icon = self.tabIcon(index)
        self.removeTab(index)
        window = QMainWindow()
        window.setWindowTitle(title)
        window.setCentralWidget(widget)
        window.resize(900, 600)
        window.setAttribute(Qt.WA_DeleteOnClose, False)
        original_title = title
        def on_close(event):
            new_index = self.addTab(widget, icon, original_title)
            if "Home" not in original_title:
                self._install_close_button(new_index)
            self.setCurrentWidget(widget)
            event.accept()
            self._detached_windows.remove(window)
        window.closeEvent = on_close
        window.show()
        self._detached_windows.append(window)

    def cleanup_detached(self) -> None:
        for w in list(self._detached_windows):
            try:
                w.close()
            except Exception:
                pass
        self._detached_windows.clear()

    # ── plus button + rename ──────────────────────────────────────────────────

    def _on_plus_clicked(self) -> None:
        """Show menu for creating a new session from the '+' button."""
        menu = QMenu()
        try:
            from PySide6.QtGui import QAction
        except ImportError:
            from PySide6.QtWidgets import QAction

        actions = [
            (_("New SSH Session"), "ssh"),
            (_("New Telnet Session"), "telnet"),
            (_("New RDP Session"), "rdp"),
            (_("New VNC Session"), "vnc"),
            (_("New Local Terminal"), "terminal"),
        ]
        for text, icon_id in actions:
            action = QAction(text, self)
            action.triggered.connect(lambda checked, t=text: self._request_new_by_label(t))
            action.setIcon(session_icon(icon_id))
            menu.addAction(action)

        menu.exec(self._plus_button.mapToGlobal(self._plus_button.rect().bottomLeft()))

    def _request_new_by_label(self, label: str) -> None:
        """Route '+' menu action to the new_session_callback."""
        if not self._new_session_callback:
            return
        from openadmindesk.core.profile import SessionType
        mapping = {
            "SSH": SessionType.SSH,
            "Telnet": SessionType.TELNET,
            "RDP": SessionType.RDP,
            "VNC": SessionType.VNC,
            "Local Terminal": SessionType.LOCAL_SHELL,
        }
        for key, st in mapping.items():
            if key in label:
                self._new_session_callback(st, None)
                return
        self._new_session_callback(SessionType.SSH, None)

    def _tab_rename(self, index: int) -> None:
        """Rename tab on double-click."""
        old_text = self.tabText(index)
        # Don't rename the home tab
        if "Home" in old_text:
            return
        new_text, ok = QInputDialog.getText(
            self, _("Rename Tab"), _("New name:"), text=old_text
        )
        if ok and new_text.strip():
            self.setTabText(index, new_text.strip())

    def connected_ssh_tabs(self) -> List[SshTerminalTab]:
        """Return all SSH terminal tabs that are currently connected."""
        result = []
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, SshTerminalTab) and w._connected:
                result.append(w)
        return result

    def all_ssh_tabs(self) -> List[SshTerminalTab]:
        """Return all SSH terminal tabs (connected or not)."""
        result = []
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, SshTerminalTab):
                result.append(w)
        return result
