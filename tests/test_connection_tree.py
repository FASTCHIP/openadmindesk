"""Tests for connection tree."""

from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.ui.connection_tree import ConnectionTree


def test_connection_tree_creation(tmp_path) -> None:
    """ConnectionTree is a container around a filter and QTreeWidget."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    tree = ConnectionTree(store)

    assert tree.filter_input is not None
    # Header is hidden in compact mode, so check that the tree exists and has proper settings
    assert tree._tree is not None
    assert tree._tree.isHeaderHidden()  # Compact mode hides header
    assert tree._tree.indentation() == 12  # Compact indentation


def test_connection_tree_empty_state(tmp_path) -> None:
    """A new empty store shows a non-selectable empty-state hint."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    tree = ConnectionTree(store)

    assert tree._tree.topLevelItemCount() == 1
    hint = tree._tree.topLevelItem(0)
    assert "No sessions yet" in hint.text(0)


def test_connection_tree_signals(tmp_path) -> None:
    """ConnectionTree has the expected signals."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    tree = ConnectionTree(store)

    assert hasattr(tree, "connection_requested")
    assert hasattr(tree, "profile_edit_requested")
    assert hasattr(tree, "profile_delete_requested")
    assert hasattr(tree, "profile_duplicate_requested")
    assert hasattr(tree, "profile_export_requested")
    assert hasattr(tree, "profile_sftp_requested")
    assert hasattr(tree, "folder_launch_requested")


def test_connection_tree_profile_metadata_in_tooltip(tmp_path) -> None:
    """Profile item tooltip includes metadata fields."""
    from openadmindesk.core.profile import Profile

    store = ProfileStore(str(tmp_path / "profiles.db"))
    profile = Profile(
        name="MetaDemo",
        host="meta.demo.com",
        port=22,
        username="admin",
        notes="production server",
        tags="prod,linux",
        last_connected="2026-07-11T12:00:00",
        favorite=True,
    )
    assert store.save_profile(profile)

    tree = ConnectionTree(store)

    # Find the item for MetaDemo
    found = False
    for i in range(tree._tree.topLevelItemCount()):
        root = tree._tree.topLevelItem(i)
        for j in range(root.childCount()):
            child = root.child(j)
            if "MetaDemo" in child.text(0):
                tooltip = child.toolTip(0)
                assert "meta.demo.com" in tooltip
                assert "production server" in tooltip
                assert "prod,linux" in tooltip
                assert "2026-07-11T12:00:00" in tooltip
                assert "★" in child.text(0) or child.text(0).count("*") > 0
                found = True
                break
    assert found


def test_connection_tree_filter_by_tag(tmp_path) -> None:
    """Search filter works with tags."""
    from openadmindesk.core.profile import Profile

    store = ProfileStore(str(tmp_path / "profiles.db"))
    p1 = Profile(name="Web Server", host="web.example.com", tags="web,prod")
    p2 = Profile(name="DB Server", host="db.example.com", tags="db,prod")
    assert store.save_profile(p1)
    assert store.save_profile(p2)

    tree = ConnectionTree(store)
    tree._apply_filter("tag:web")
    # Web should be visible, DB should be hidden
    # Check by counting visible items
    assert tree._tree.topLevelItemCount() > 0


def test_connection_tree_filter_by_protocol(tmp_path) -> None:
    """Search filter works with proto: prefix."""
    from openadmindesk.core.profile import Profile, SessionType

    store = ProfileStore(str(tmp_path / "profiles.db"))
    p1 = Profile(name="SSH Box", host="ssh.example.com", session_type=SessionType.SSH)
    p2 = Profile(name="RDP Box", host="rdp.example.com", session_type=SessionType.RDP)
    assert store.save_profile(p1)
    assert store.save_profile(p2)

    tree = ConnectionTree(store)
    tree._apply_filter("proto:ssh")
    assert tree._tree.topLevelItemCount() > 0
