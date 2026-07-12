"""Workspace container that can host multiple tabbed panes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
)
from PySide6.QtCore import QEvent, Qt
from typing import List
from openadmindesk.ui.tabbed_workspace import TabbedWorkspace


class WorkspaceContainer(QWidget):
    """Container that manages multiple tabbed workspaces in different layouts."""

    def __init__(self) -> None:
        """Initialize the workspace container."""
        super().__init__()
        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # Main container for panes
        self._pane_container = QStackedWidget()
        self.layout().addWidget(self._pane_container)
        
        # Current layout mode
        self._layout_mode = "single"
        self._active_workspace: TabbedWorkspace | None = None
        
        # Create single pane layout (default)
        self._single_pane = TabbedWorkspace()
        self._pane_container.addWidget(self._single_pane)
        
        # Create horizontal split layout
        self._horizontal_pane = self._create_horizontal_split()
        self._pane_container.addWidget(self._horizontal_pane)
        
        # Create vertical split layout
        self._vertical_pane = self._create_vertical_split()
        self._pane_container.addWidget(self._vertical_pane)
        
        # Create grid layout (4 panes)
        self._grid_pane = self._create_grid_layout()
        self._pane_container.addWidget(self._grid_pane)
        
        # Set default to single pane
        self.set_layout_mode("single")
        self._install_workspace_tracking()

    def _create_horizontal_split(self) -> QWidget:
        """Create horizontal split layout with two panes."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        pane1 = TabbedWorkspace()
        pane2 = TabbedWorkspace()
        
        splitter.addWidget(pane1)
        splitter.addWidget(pane2)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        # Store panes for reference
        container.pane1 = pane1
        container.pane2 = pane2
        
        return container

    def _create_vertical_split(self) -> QWidget:
        """Create vertical split layout with two panes."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        pane1 = TabbedWorkspace()
        pane2 = TabbedWorkspace()
        
        splitter.addWidget(pane1)
        splitter.addWidget(pane2)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        # Store panes for reference
        container.pane1 = pane1
        container.pane2 = pane2
        
        return container

    def _create_grid_layout(self) -> QWidget:
        """Create grid layout with four panes."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Top row splitter
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Bottom row splitter
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # Create four panes
        pane1 = TabbedWorkspace()
        pane2 = TabbedWorkspace()
        pane3 = TabbedWorkspace()
        pane4 = TabbedWorkspace()
        
        top_splitter.addWidget(pane1)
        top_splitter.addWidget(pane2)
        bottom_splitter.addWidget(pane3)
        bottom_splitter.addWidget(pane4)
        
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)
        
        # Add splitters to main layout
        layout.addWidget(top_splitter)
        layout.addWidget(bottom_splitter)
        
        # Store panes for reference
        container.pane1 = pane1
        container.pane2 = pane2
        container.pane3 = pane3
        container.pane4 = pane4
        
        return container

    def set_layout_mode(self, mode: str) -> None:
        """Set the workspace layout mode."""
        if mode not in ["single", "horizontal", "vertical", "grid"]:
            return

        tabs = []
        if hasattr(self, "_pane_container"):
            for workspace in self.get_all_workspaces():
                tabs.extend(workspace.extract_content_tabs())

        self._layout_mode = mode
        
        # Show the appropriate pane layout
        if mode == "single":
            self._pane_container.setCurrentWidget(self._single_pane)
        elif mode == "horizontal":
            self._pane_container.setCurrentWidget(self._horizontal_pane)
        elif mode == "vertical":
            self._pane_container.setCurrentWidget(self._vertical_pane)
        elif mode == "grid":
            self._pane_container.setCurrentWidget(self._grid_pane)

        target_workspaces = self.get_all_workspaces()
        target = target_workspaces[0]
        for widget, icon, title in tabs:
            target.append_existing_tab(widget, icon, title)
        if tabs:
            target.setCurrentIndex(target.count() - 1)
            target._focus_current_terminal(target.currentIndex())
        self._active_workspace = target
        
        # Set callback for all workspaces in the current layout
        self._set_callback_for_current_workspaces()

    def get_current_layout_mode(self) -> str:
        """Get the current layout mode."""
        return self._layout_mode

    def get_active_workspace(self) -> TabbedWorkspace:
        """Get the currently active workspace (the one with focus)."""
        if self._active_workspace in self.get_all_workspaces():
            return self._active_workspace
        if self._layout_mode == "single":
            return self._single_pane
        elif self._layout_mode == "horizontal":
            if self._workspace_has_focus(self._horizontal_pane.pane1):
                return self._horizontal_pane.pane1
            elif self._workspace_has_focus(self._horizontal_pane.pane2):
                return self._horizontal_pane.pane2
            return self._horizontal_pane.pane1
        elif self._layout_mode == "vertical":
            if self._workspace_has_focus(self._vertical_pane.pane1):
                return self._vertical_pane.pane1
            elif self._workspace_has_focus(self._vertical_pane.pane2):
                return self._vertical_pane.pane2
            return self._vertical_pane.pane1
        elif self._layout_mode == "grid":
            active = self._grid_pane
            if self._workspace_has_focus(active.pane1):
                return active.pane1
            elif self._workspace_has_focus(active.pane2):
                return active.pane2
            elif self._workspace_has_focus(active.pane3):
                return active.pane3
            elif self._workspace_has_focus(active.pane4):
                return active.pane4
            return active.pane1
        
        return self._single_pane

    def get_all_workspaces(self) -> List[TabbedWorkspace]:
        """Get all workspace widgets in the current layout."""
        if self._layout_mode == "single":
            return [self._single_pane]
        elif self._layout_mode == "horizontal":
            return [self._horizontal_pane.pane1, self._horizontal_pane.pane2]
        elif self._layout_mode == "vertical":
            return [self._vertical_pane.pane1, self._vertical_pane.pane2]
        elif self._layout_mode == "grid":
            return [self._grid_pane.pane1, self._grid_pane.pane2, 
                   self._grid_pane.pane3, self._grid_pane.pane4]
        
        return [self._single_pane]

    def _all_physical_workspaces(self) -> List[TabbedWorkspace]:
        return [
            self._single_pane,
            self._horizontal_pane.pane1,
            self._horizontal_pane.pane2,
            self._vertical_pane.pane1,
            self._vertical_pane.pane2,
            self._grid_pane.pane1,
            self._grid_pane.pane2,
            self._grid_pane.pane3,
            self._grid_pane.pane4,
        ]

    def _install_workspace_tracking(self) -> None:
        for workspace in self._all_physical_workspaces():
            workspace.setFocusPolicy(Qt.StrongFocus)
            workspace.installEventFilter(self)
            workspace.tabBar().installEventFilter(self)
            workspace.currentChanged.connect(
                lambda _index, ws=workspace: self._mark_active_workspace(ws)
            )
            workspace.tabBar().tabBarClicked.connect(
                lambda _index, ws=workspace: self._mark_active_workspace(ws)
            )
        self._active_workspace = self._single_pane

    def _mark_active_workspace(self, workspace: TabbedWorkspace) -> None:
        self._active_workspace = workspace

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            for workspace in self._all_physical_workspaces():
                if obj in (workspace, workspace.tabBar()):
                    self._mark_active_workspace(workspace)
                    break
        return super().eventFilter(obj, event)

    def _workspace_has_focus(self, workspace: TabbedWorkspace) -> bool:
        focused = self.focusWidget()
        while focused is not None:
            if focused is workspace:
                return True
            focused = focused.parentWidget()
        return False

    def set_new_session_callback(self, callback: callable) -> None:
        """Set the callback for new session requests."""
        self._new_session_callback = callback
        # Set callback for all workspaces in the current layout
        self._set_callback_for_current_workspaces()

    def _set_callback_for_current_workspaces(self) -> None:
        """Set the callback for all workspaces in the current layout."""
        if not hasattr(self, '_new_session_callback') or self._new_session_callback is None:
            return
            
        workspaces = self.get_all_workspaces()
        for ws in workspaces:
            ws._new_session_callback = self._new_session_callback
