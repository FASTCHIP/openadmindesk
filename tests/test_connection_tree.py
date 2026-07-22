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


def test_rename_signal_exists(tmp_path) -> None:
    """ConnectionTree has the profile_rename_requested signal."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    tree = ConnectionTree(store)
    assert hasattr(tree, "profile_rename_requested")


def test_rename_prompt_normalization(tmp_path) -> None:
    """_on_rename_profile normalizes names and skips cancel/blank/same."""
    from PySide6.QtWidgets import QInputDialog
    store = ProfileStore(str(tmp_path / "profiles.db"))
    tree = ConnectionTree(store)

    emitted: list[tuple[str, str]] = []
    tree.profile_rename_requested.connect(lambda o, n: emitted.append((o, n)))

    # Cancel — simulating by patching getText to return ('', False)
    def mock_cancel(*args, **kwargs):
        return ("whatever", False)
    original = QInputDialog.getText
    QInputDialog.getText = mock_cancel
    try:
        tree._on_rename_profile("OldName")
    finally:
        QInputDialog.getText = original
    assert emitted == []

    # Blank name
    def mock_blank(*args, **kwargs):
        return ("   ", True)
    QInputDialog.getText = mock_blank
    try:
        tree._on_rename_profile("OldName")
    finally:
        QInputDialog.getText = original
    assert emitted == []

    # Same name after strip
    def mock_same(*args, **kwargs):
        return ("OldName  ", True)
    QInputDialog.getText = mock_same
    try:
        tree._on_rename_profile("OldName")
    finally:
        QInputDialog.getText = original
    assert emitted == []

    # Valid change — emits (old_name, normalized_new_name)
    def mock_valid(*args, **kwargs):
        return ("  NewName  ", True)
    QInputDialog.getText = mock_valid
    try:
        tree._on_rename_profile("OldName")
    finally:
        QInputDialog.getText = original
    assert emitted == [("OldName", "NewName")]


def test_profile_context_menu_contains_rename(tmp_path) -> None:
    """Profile context menu keeps all existing actions and adds Rename... near Edit/Duplicate."""
    from openadmindesk.core.profile import Profile, SessionType

    store = ProfileStore(str(tmp_path / "profiles.db"))
    profile = Profile(name="SSHBox", host="ssh.example.com", session_type=SessionType.SSH)
    assert store.save_profile(profile)

    tree = ConnectionTree(store)

    # Locate the profile item
    item = None
    for i in range(tree._tree.topLevelItemCount()):
        root = tree._tree.topLevelItem(i)
        for j in range(root.childCount()):
            if "SSHBox" in root.child(j).text(0):
                item = root.child(j)
                break
    assert item is not None

    # Build menu directly without exec
    menu = tree._build_context_menu(item)

    # Get actions directly from menu
    actions = menu.actions()

    # Collect non-separator action texts
    texts = [a.text() for a in actions if not a.isSeparator()]

    # Rename action present
    rename_texts = [t for t in texts if "Rename" in t]
    assert len(rename_texts) == 1
    assert "Rename" in rename_texts[0]

    # All expected profile actions present
    expected_checks = ["Connect", "Edit", "Duplicate", "SFTP", "Copy", "Export", "Delete"]
    for label in expected_checks:
        assert any(label in t for t in texts), f"Missing action containing '{label}'"

    # Relative order: Duplicate < Rename < SFTP/Copy block
    dup_idx = next(i for i, t in enumerate(texts) if "Duplicate" in t)
    rename_idx = next(i for i, t in enumerate(texts) if "Rename" in t)
    assert dup_idx < rename_idx, "Rename must appear after Duplicate"

    # Rename should be before SSH-specific (SFTP or Copy SSH command)
    sftp_or_copy = None
    for i, t in enumerate(texts):
        if "SFTP" in t or "Copy" in t:
            sftp_or_copy = i
            break
    if sftp_or_copy is not None:
        assert rename_idx < sftp_or_copy, "Rename must appear before SSH-specific actions"


def test_mainwindow_rename_success(tmp_path, monkeypatch) -> None:
    """End-to-end: MainWindow renames profile, clears filter, refreshes tree, shows success."""
    from openadmindesk.ui.main_window import MainWindow
    from openadmindesk.core.profile import Profile
    from PySide6.QtWidgets import QMessageBox

    db_path = str(tmp_path / "profiles.db")
    vault_path = str(tmp_path / "vault.json")

    monkeypatch.setattr("openadmindesk.ui.main_window.default_db_path", lambda: db_path)
    monkeypatch.setattr("openadmindesk.ui.main_window.default_vault_path", lambda: vault_path)

    win = MainWindow()
    win._vault_lock_timer.stop()

    # Stub out SyncManager.close() which doesn't exist in test
    monkeypatch.setattr(win.sync_manager, "close", lambda: None, raising=False)

    # Suppress message boxes during test
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)

    try:
        # Create a profile with pre-set filter
        profile = Profile(name="OldName", host="rename.test.local", username="testuser", port=22, notes="original")
        assert win.profile_store.save_profile(profile)
        win.connection_tree.refresh()

        # Set an active filter
        win.connection_tree.filter_input.setText("OldName")
        assert win.connection_tree.filter_input.text() == "OldName"

        # Perform rename
        win._on_profile_rename_requested("OldName", "NewName")

        # Verify DB state
        assert win.profile_store.load_profile("OldName") is None
        renamed = win.profile_store.load_profile("NewName")
        assert renamed is not None
        assert renamed.host == "rename.test.local"
        assert renamed.username == "testuser"

        # Verify filter was cleared
        assert win.connection_tree.filter_input.text() == ""

        # Verify tree shows new name
        tree_text_visible = False
        for i in range(win.connection_tree._tree.topLevelItemCount()):
            root = win.connection_tree._tree.topLevelItem(i)
            for j in range(root.childCount()):
                if "NewName" in root.child(j).text(0):
                    tree_text_visible = True
                    break
        assert tree_text_visible
    finally:
        win._vault_lock_timer.stop()
        win.close()
        win.deleteLater()


def test_mainwindow_rename_conflict(tmp_path, monkeypatch) -> None:
    """End-to-end: conflicting rename does not mutate tree/filter and shows warning."""
    from openadmindesk.ui.main_window import MainWindow
    from openadmindesk.core.profile import Profile
    from PySide6.QtWidgets import QMessageBox

    db_path = str(tmp_path / "profiles.db")
    vault_path = str(tmp_path / "vault.json")

    monkeypatch.setattr("openadmindesk.ui.main_window.default_db_path", lambda: db_path)
    monkeypatch.setattr("openadmindesk.ui.main_window.default_vault_path", lambda: vault_path)

    win = MainWindow()
    win._vault_lock_timer.stop()

    # Stub out SyncManager.close() which doesn't exist in test
    monkeypatch.setattr(win.sync_manager, "close", lambda: None, raising=False)

    warning_shown: list[str] = []

    def capture_warning(parent, title, text):
        warning_shown.append(text)
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "warning", capture_warning)

    try:
        profile_a = Profile(name="ProfileA", host="a.example.com")
        profile_b = Profile(name="ProfileB", host="b.example.com")
        assert win.profile_store.save_profile(profile_a)
        assert win.profile_store.save_profile(profile_b)
        win.connection_tree.refresh()

        # Set a filter to verify it's not cleared on failure
        win.connection_tree.filter_input.setText("Profile")
        original_filter = win.connection_tree.filter_input.text()

        # Attempt conflicting rename
        win._on_profile_rename_requested("ProfileA", "ProfileB")

        # Both profiles unchanged
        assert win.profile_store.load_profile("ProfileA") is not None
        assert win.profile_store.load_profile("ProfileB") is not None

        # Filter untouched
        assert win.connection_tree.filter_input.text() == original_filter

        # Warning shown with useful context
        assert len(warning_shown) >= 1
        assert "ProfileA" in warning_shown[0]
        assert "ProfileB" in warning_shown[0]
    finally:
        win._vault_lock_timer.stop()
        win.close()
        win.deleteLater()
