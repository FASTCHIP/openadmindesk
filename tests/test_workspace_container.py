"""Tests for workspace container with multiple panes."""

from openadmindesk.ui.workspace_container import WorkspaceContainer
from openadmindesk.ui.tabbed_workspace import TabbedWorkspace
from openadmindesk.core.profile import Profile


def test_workspace_container_creation() -> None:
    """Workspace container starts with single pane layout."""
    container = WorkspaceContainer()

    assert container.get_current_layout_mode() == "single"
    workspaces = container.get_all_workspaces()
    assert len(workspaces) == 1
    assert isinstance(workspaces[0], TabbedWorkspace)


def test_workspace_container_layout_switching() -> None:
    """Workspace container can switch between different layout modes."""
    container = WorkspaceContainer()

    # Test single layout
    container.set_layout_mode("single")
    assert container.get_current_layout_mode() == "single"
    assert len(container.get_all_workspaces()) == 1

    # Test horizontal layout
    container.set_layout_mode("horizontal")
    assert container.get_current_layout_mode() == "horizontal"
    workspaces = container.get_all_workspaces()
    assert len(workspaces) == 2
    assert all(isinstance(ws, TabbedWorkspace) for ws in workspaces)

    # Test vertical layout
    container.set_layout_mode("vertical")
    assert container.get_current_layout_mode() == "vertical"
    workspaces = container.get_all_workspaces()
    assert len(workspaces) == 2
    assert all(isinstance(ws, TabbedWorkspace) for ws in workspaces)

    # Test grid layout
    container.set_layout_mode("grid")
    assert container.get_current_layout_mode() == "grid"
    workspaces = container.get_all_workspaces()
    assert len(workspaces) == 4
    assert all(isinstance(ws, TabbedWorkspace) for ws in workspaces)


def test_workspace_container_new_session_callback() -> None:
    """New session callback is set for all workspaces."""
    container = WorkspaceContainer()
    callback_called = []

    def test_callback(session_type, parent_folder):
        callback_called.append((session_type, parent_folder))

    container.set_new_session_callback(test_callback)

    # Test callback is set for single layout
    container.set_layout_mode("single")
    workspaces = container.get_all_workspaces()
    for ws in workspaces:
        assert ws._new_session_callback is test_callback

    # Test callback is set for horizontal layout
    container.set_layout_mode("horizontal")
    workspaces = container.get_all_workspaces()
    for ws in workspaces:
        assert ws._new_session_callback is test_callback


def test_workspace_container_active_workspace() -> None:
    """Active workspace can be retrieved."""
    container = WorkspaceContainer()

    # In single layout, active workspace is the single pane
    container.set_layout_mode("single")
    active = container.get_active_workspace()
    assert isinstance(active, TabbedWorkspace)


def test_layout_switch_preserves_open_tabs_in_single() -> None:
    container = WorkspaceContainer()
    profile1 = Profile(name="one", host="one.example.com")
    profile2 = Profile(name="two", host="two.example.com")

    single = container.get_active_workspace()
    single.add_ssh_terminal_tab(profile1)
    single.add_ssh_terminal_tab(profile2)

    container.set_layout_mode("horizontal")
    left, right = container.get_all_workspaces()
    assert left.count() == 3
    assert right.count() == 1
    assert any("one" in left.tabText(i) for i in range(left.count()))
    assert any("two" in left.tabText(i) for i in range(left.count()))

    container.set_layout_mode("single")
    single = container.get_active_workspace()
    assert single.count() == 3
    assert any("one" in single.tabText(i) for i in range(single.count()))
    assert any("two" in single.tabText(i) for i in range(single.count()))


def test_split_default_active_workspace_is_first_pane() -> None:
    container = WorkspaceContainer()
    container.set_layout_mode("horizontal")

    workspaces = container.get_all_workspaces()

    assert container.get_active_workspace() is workspaces[0]


def test_tabbed_workspace_focuses_terminal_when_current_changes() -> None:
    workspace = TabbedWorkspace()
    profile = Profile(name="focus", host="focus.example.com")
    workspace.add_ssh_terminal_tab(profile)
    tab = workspace.currentWidget()
    focused = []
    tab.terminal.setFocus = lambda *args: focused.append(args)

    workspace._focus_current_terminal(workspace.currentIndex())

    assert focused
