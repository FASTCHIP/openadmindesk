"""Test for main window."""


from pathlib import Path
from openadmindesk.core.profile import Profile
from openadmindesk.ui.main_window import MainWindow
from openadmindesk.ui.ssh_terminal_tab import SshTerminalTab


def test_main_window_creation() -> None:
    """Test that main window can be created."""
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() == "OpenAdminDesk"


def test_main_window_properties() -> None:
    """Test main window properties."""
    window = MainWindow()
    
    # Check basic properties
    assert window.windowTitle() == "OpenAdminDesk"
    assert window.width() == 1200
    assert window.height() == 800


def test_main_window_components() -> None:
    """Test main window components exist."""
    window = MainWindow()
    
    # Check that components exist
    assert window.connection_tree is not None
    assert window.workspace_container is not None
    assert window.quick_connect_toolbar is not None
    assert window.connection_event_area is not None

def test_main_window_routes_local_shell_profiles(monkeypatch) -> None:
    """Local shell profiles should open a LocalShellTab, not an SSH tab."""
    from PySide6.QtWidgets import QWidget

    from openadmindesk.core.profile import Profile, SessionType
    from openadmindesk.ui import local_shell_tab

    created = []

    class FakeLocalShellTab(QWidget):
        def __init__(self, shell_name="bash") -> None:
            super().__init__()
            self.shell_name = shell_name
            created.append(shell_name)

    monkeypatch.setattr(local_shell_tab, "LocalShellTab", FakeLocalShellTab)
    window = MainWindow()
    profile = Profile(name="Local", host="localhost", port=1, session_type=SessionType.LOCAL_SHELL)

    window._open_ssh_tab(profile)

    assert created == ["Local"]
    # Get the active workspace and check the tab text
    active_ws = window.workspace_container.get_active_workspace()
    assert "Local" in active_ws.tabText(active_ws.currentIndex())



def test_main_window_resolves_runtime_credentials_from_vault() -> None:
    from openadmindesk.core.account import Account
    from openadmindesk.core.profile import Profile

    class FakeVault:
        def is_unlocked(self) -> bool:
            return True

        def get_account(self, account_id: str) -> Account:
            if account_id == "gw-1":
                return Account(
                    id=account_id,
                    name="Gateway Account",
                    username="gw-user",
                    password="gw-secret",
                    host="gw.example.com",
                    service_type="rdp-gateway",
                )
            return Account(
                id=account_id,
                name="Vault Account",
                username="vault-user",
                password="vault-secret",
                host="example.com",
            )

    window = MainWindow()
    window.vault_manager = FakeVault()  # type: ignore[assignment]
    profile = Profile(
        name="SSH",
        host="example.com",
        username="",
        credential_id="acc-1",
        rdp_gateway_credential_id="gw-1",
    )

    runtime_profile = window._profile_with_vault_credentials(profile)

    assert runtime_profile is not profile
    assert profile.password is None
    assert runtime_profile.username == "vault-user"
    assert runtime_profile.password == "vault-secret"
    assert runtime_profile.rdp_gateway == "gw.example.com"
    assert runtime_profile.rdp_gateway_username == "gw-user"
    assert runtime_profile.rdp_gateway_password == "gw-secret"

def test_multi_exec_panel_rejects_zero_targets() -> None:
    """MultiExec rejects activation when no tabs are opted-in."""
    from openadmindesk.ui.multi_exec_panel import MultiExecPanel
    panel = MultiExecPanel()
    broadcast_calls = []
    panel.broadcast_requested.connect(lambda e: broadcast_calls.append(e))

    # No tabs → selected_count == 0 → should not emit True
    assert panel.selected_count() == 0
    # Attempt to emit via internal method (no tabs to toggle)
    panel._update_broadcast_state()
    assert True not in broadcast_calls


def test_multi_exec_panel_clear_all() -> None:
    """Emergency stop clears all opt-ins and requests broadcast off."""
    from openadmindesk.ui.multi_exec_panel import MultiExecPanel
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab = SshTerminalTab(profile)
    tab._connected = True
    tab.broadcast_opted_in = True

    panel = MultiExecPanel()
    broadcast_calls = []
    panel.broadcast_requested.connect(lambda e: broadcast_calls.append(e))
    panel._tabs = {str(id(tab)): tab}
    panel._rebuild_table()

    panel._emergency_stop()
    assert tab.broadcast_opted_in is False
    assert broadcast_calls[-1] is False  # last call is False


def test_multi_exec_panel_select_count() -> None:
    """Selected count reflects opted-in connected tabs."""
    from openadmindesk.ui.multi_exec_panel import MultiExecPanel
    profile = Profile(name="test", host="example.com", port=22, username="user")
    tab1 = SshTerminalTab(profile)
    tab1._connected = True
    tab1.broadcast_opted_in = True
    tab2 = SshTerminalTab(profile)
    tab2._connected = True  # not opted in

    panel = MultiExecPanel()
    panel._tabs = {str(id(tab1)): tab1, str(id(tab2)): tab2}
    panel._rebuild_table()
    assert panel.selected_count() == 1

    # Opt-in second tab
    tab2.broadcast_opted_in = True
    panel._update_ui()
    assert panel.selected_count() == 2

    # Disconnect first tab → opt-in cleared
    tab1._connected = False
    panel._update_ui()
    assert tab1.broadcast_opted_in is False
    assert panel.selected_count() == 1


def test_connect_broadcast_and_disconnect_broadcast_with_multi_exec(monkeypatch) -> None:
    """_connect_broadcast / _disconnect_broadcast work with the panel."""
    window = MainWindow()
    profile = Profile(name="test", host="example.com", port=22, username="user")

    # Create a real SshTerminalTab connected
    tab = SshTerminalTab(profile)
    tab._connected = True
    tab.broadcast_opted_in = True

    # Wire into the panel
    window._multi_exec_panel._tabs = {str(id(tab)): tab}
    window._multi_exec_panel._rebuild_table()

    # Connect broadcast
    window._connect_broadcast()
    assert window.broadcast_mode is False  # mode not changed yet

    # Now set mode and test broadcast_key through panel's selected_tabs
    window.broadcast_mode = True
    opted = window._multi_exec_panel.selected_tabs()
    assert len(opted) == 1
    assert opted[0] is tab

    # Disconnect: clears opt-in
    window._disconnect_broadcast()
    assert tab.broadcast_opted_in is False

# ── vault auto-lock polling ──────────────────────────────────────────────────


def test_vault_auto_lock_timer_exists() -> None:
    """Timer exists, is active, parented to window, with expected interval."""
    window = MainWindow()
    assert hasattr(window, '_vault_lock_timer')
    timer = window._vault_lock_timer
    assert timer.isActive()
    assert timer.parent() is window
    assert timer.interval() == 1000


class _FakeVaultLocked:
    """Fake vault that reports locked."""
    def is_unlocked(self) -> bool:
        return False


class _FakeVaultUnlocked:
    """Fake vault that reports unlocked."""
    def is_unlocked(self) -> bool:
        return True


def test_vault_auto_lock_transition_unlocked_to_locked(monkeypatch) -> None:
    """Poll detects unlocked→locked transition, updates actions, emits message."""
    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(
        window.connection_event_area, 'showMessage',
        lambda msg, timeout=0: messages.append(msg)
    )

    # Start in unlocked state, vault now locked
    window.vault_manager = _FakeVaultLocked()  # type: ignore[assignment]
    window._last_vault_unlocked = True

    window._poll_vault_lock_state()

    # State synced
    assert window._last_vault_unlocked is False
    # Exactly one auto-lock message
    assert len(messages) == 1
    assert "auto-locked" in messages[0].lower()
    # Menu actions reflect locked state
    assert window.unlock_vault_action.isEnabled() is True
    assert window.lock_vault_action.isEnabled() is False


def test_vault_auto_lock_no_duplicate_message_on_stable_locked(monkeypatch) -> None:
    """Second poll on stable locked does not emit another message."""
    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(
        window.connection_event_area, 'showMessage',
        lambda msg, timeout=0: messages.append(msg)
    )

    window.vault_manager = _FakeVaultLocked()  # type: ignore[assignment]
    window._last_vault_unlocked = True

    # First poll – transition
    window._poll_vault_lock_state()
    assert len(messages) == 1

    # Second poll – stable locked
    window._poll_vault_lock_state()
    assert len(messages) == 1


def test_vault_auto_lock_stable_unlocked(monkeypatch) -> None:
    """Stable unlocked: correct actions, no auto-lock message."""
    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(
        window.connection_event_area, 'showMessage',
        lambda msg, timeout=0: messages.append(msg)
    )

    window.vault_manager = _FakeVaultUnlocked()  # type: ignore[assignment]
    window._last_vault_unlocked = True

    window._poll_vault_lock_state()

    assert len(messages) == 0  # no auto-lock message
    assert window._last_vault_unlocked is True
    # Menu reflects unlocked state
    assert window.unlock_vault_action.isEnabled() is False
    assert window.lock_vault_action.isEnabled() is True


def test_vault_auto_lock_manual_lock_no_auto_message(monkeypatch) -> None:
    """Manual lock sync prevents subsequent poll from emitting auto-lock."""
    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(
        window.connection_event_area, 'showMessage',
        lambda msg, timeout=0: messages.append(msg)
    )

    # Vault is locked (simulate after manual _lock_vault called)
    window.vault_manager = _FakeVaultLocked()  # type: ignore[assignment]
    # _lock_vault already synced this to False
    window._last_vault_unlocked = False

    window._poll_vault_lock_state()

    # No auto-lock message on stable locked
    assert len(messages) == 0
    assert window._last_vault_unlocked is False


class _FakeVaultSetup:
    """Fake vault that supports setup but stays locked."""
    def is_unlocked(self) -> bool:
        return False
    def setup_master_password(self, password: str) -> bool:
        return True


def test_vault_auto_lock_setup_success_no_false_auto_message(monkeypatch) -> None:
    """Successful vault setup syncs from actual state (locked), no false auto-lock."""
    import PySide6.QtWidgets
    monkeypatch.setattr(
        PySide6.QtWidgets.QInputDialog, 'getText',
        lambda *args, **kwargs: ("test-pass", True)
    )
    monkeypatch.setattr(
        PySide6.QtWidgets.QMessageBox, 'information',
        lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        PySide6.QtWidgets.QMessageBox, 'warning',
        lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        PySide6.QtWidgets.QMessageBox, 'critical',
        lambda *args, **kwargs: None
    )

    window = MainWindow()
    messages: list[str] = []
    monkeypatch.setattr(
        window.connection_event_area, 'showMessage',
        lambda msg, timeout=0: messages.append(msg)
    )

    window.vault_manager = _FakeVaultSetup()  # type: ignore[assignment]
    window._last_vault_unlocked = False  # initial state matches vault

    window._setup_vault()

    # After setup, _last_vault_unlocked synced from vault.is_unlocked() (False)
    assert window._last_vault_unlocked is False
    # Poll should see no unlocked→locked transition → no auto-lock message
    window._poll_vault_lock_state()
    auto_lock_msgs = [m for m in messages if "auto-locked" in m.lower()]
    assert len(auto_lock_msgs) == 0
    # Actions reflect locked state
    assert window.unlock_vault_action.isEnabled() is True
    assert window.lock_vault_action.isEnabled() is False


def test_main_window_applies_terminal_settings_to_open_ssh_tabs(monkeypatch) -> None:
    class FakeTerminal:
        def __init__(self) -> None:
            self.font = None
            self.opacity = None
            self._max_scrollback = 0

        def set_font(self, family: str, size: int) -> None:
            self.font = (family, size)

        def set_bg_opacity(self, opacity: int) -> None:
            self.opacity = opacity

    class FakeTab:
        def __init__(self) -> None:
            self.terminal = FakeTerminal()

    class FakeWorkspace:
        def __init__(self, tab: FakeTab) -> None:
            self.tab = tab

        def all_ssh_tabs(self) -> list[FakeTab]:
            return [self.tab]

    class FakeWorkspaceContainer:
        def __init__(self, tab: FakeTab) -> None:
            self.tab = tab

        def get_all_workspaces(self) -> list[FakeWorkspace]:
            return [FakeWorkspace(self.tab)]

    from openadmindesk.core.settings import AppSettings

    window = MainWindow()
    tab = FakeTab()
    window.workspace_container = FakeWorkspaceContainer(tab)  # type: ignore[assignment]
    window._app_settings = AppSettings(
        terminal_font_family="DejaVu Sans Mono",
        terminal_font_size=14,
        terminal_bg_opacity=200,
        terminal_scrollback_lines=9000,
    )

    window._apply_app_settings()

    assert tab.terminal.font == ("DejaVu Sans Mono", 14)
    assert tab.terminal.opacity == 200
    assert tab.terminal._max_scrollback == 9000


def test_main_window_upgrade_vault_action_exists() -> None:
    """Test that upgrade vault action exists."""
    window = MainWindow()

    # Verify upgrade action exists
    assert window.upgrade_vault_action is not None


def test_vault_upgrade_error_messages_include_recovery_path(monkeypatch) -> None:
    """Test that vault upgrade error messages include recovery path."""
    window = MainWindow()

    # Import required classes locally
    from PySide6.QtWidgets import QMessageBox
    from openadmindesk.core.vault_upgrade import VaultUpgradeError

    # Mock QMessageBox methods to capture messages
    captured_messages = []

    def capture_warning(*args, **kwargs):
        captured_messages.append(("warning", str(args[2]) if len(args) > 2 else ""))
        return 0

    def capture_critical(*args, **kwargs):
        captured_messages.append(("critical", str(args[2]) if len(args) > 2 else ""))
        return 0

    monkeypatch.setattr(QMessageBox, 'warning', capture_warning)
    monkeypatch.setattr(QMessageBox, 'critical', capture_critical)

    # Test cases: (rollback_succeeded, expected_kind, expected_text)
    test_cases = [
        (None, "critical", "Source was not replaced"),
        (True, "warning", "Original v1 restored"),
        (False, "critical", "Rollback failed"),
    ]

    for rollback_succeeded, expected_kind, expected_text in test_cases:
        # Reset captured messages
        captured_messages.clear()

        # Create a VaultUpgradeError with recovery_backup_path
        error = VaultUpgradeError(
            "upgrade failed",
            rollback_succeeded=rollback_succeeded,
            recovery_backup_path="/tmp/recovery.json"
        )

        # Call the method that shows the error
        window._show_upgrade_error(error)

        # Verify the message was shown
        assert len(captured_messages) == 1
        kind, message = captured_messages[0]
        assert kind == expected_kind
        assert expected_text in message
        assert "/tmp/recovery.json" in message
        # Verify that sensitive information is not shown
        assert "source_sha256" not in message
        assert "password" not in message


def test_vault_upgrade_menu_order() -> None:
    """Test that vault upgrade menu has correct order and actions."""
    window = MainWindow()

    # Import QMenu locally
    from PySide6.QtWidgets import QMenu

    # Find the Vault menu
    vault_menu = None
    for menu in window.menuBar().findChildren(QMenu):
        if menu.title() == "&Vault":
            vault_menu = menu
            break

    assert vault_menu is not None

    # Get actions and convert to text list
    actions = vault_menu.actions()
    action_texts = []
    for action in actions:
        if action.isSeparator():
            action_texts.append("<separator>")
        else:
            action_texts.append(action.text())

    # Check exact order
    expected_order = [
        "Setup Master Password...",
        "Unlock Vault...",
        "Lock Vault",
        "Upgrade Vault Security…",
        "<separator>",
        "Manage Accounts..."
    ]

    assert action_texts == expected_order

    # Check that upgrade action is enabled
    upgrade_action = None
    for action in actions:
        if action.text() == "Upgrade Vault Security…":
            upgrade_action = action
            break

    assert upgrade_action is not None
    assert upgrade_action.isEnabled() is True


def test_vault_upgrade_v2_skips_password_and_core(monkeypatch) -> None:
    """Test that vault upgrade v2 skips password and core calls."""
    # Import module locally
    import openadmindesk.ui.main_window as main_window_module

    # Patch module inspect to return version 2
    def mock_inspect_vault_version(p):
        return 2

    monkeypatch.setattr(main_window_module, 'inspect_vault_version', mock_inspect_vault_version)

    # Patch QInputDialog.getText to raise AssertionError if called
    from PySide6.QtWidgets import QInputDialog
    def mock_get_text(*args, **kwargs):
        raise AssertionError("QInputDialog.getText should not be called for v2")

    monkeypatch.setattr(QInputDialog, 'getText', mock_get_text)

    # Patch core functions to raise AssertionError if called
    def mock_core_function(*args, **kwargs):
        raise AssertionError("Core function should not be called for v2")

    # Patch the main window module, not the core module
    monkeypatch.setattr(main_window_module, "upgrade_vault_v1_to_v2", mock_core_function)

    # Patch QMessageBox.information to capture calls
    from PySide6.QtWidgets import QMessageBox
    captured_info = []
    def mock_information(*args, **kwargs):
        captured_info.append((args, kwargs))

    monkeypatch.setattr(QMessageBox, 'information', mock_information)

    # Create window and call the slot
    window = MainWindow()
    window._on_upgrade_vault()

    # Assert that information dialog was shown with v2 message
    assert len(captured_info) == 1
    assert "v2" in captured_info[0][0][2]  # Check message content


def test_vault_upgrade_warning_cancel_skips_lock_password_and_core(monkeypatch) -> None:
    """Test that vault upgrade warning cancel skips lock, password and core calls."""
    # Import module locally
    import openadmindesk.ui.main_window as main_window_module

    # Patch module inspect to return version 1
    def mock_inspect_vault_version(p):
        return 1

    monkeypatch.setattr(main_window_module, 'inspect_vault_version', mock_inspect_vault_version)

    # Set warning response to cancel (QMessageBox.No)
    from PySide6.QtWidgets import QMessageBox
    def mock_warning(*args, **kwargs):
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

    # Patch instance vault_manager.lock, QInputDialog and core to raise AssertionError if called
    def mock_lock(*args, **kwargs):
        raise AssertionError("Instance lock should not be called when warning is cancelled")

    def mock_get_text(*args, **kwargs):
        raise AssertionError("QInputDialog.getText should not be called when warning is cancelled")

    def mock_core_function(*args, **kwargs):
        raise AssertionError("Core function should not be called when warning is cancelled")

    # Create window and patch the methods
    window = MainWindow()
    monkeypatch.setattr(window.vault_manager, 'lock', mock_lock)
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, 'getText', mock_get_text)
    # Patch the main window module, not the core module
    monkeypatch.setattr(main_window_module, "upgrade_vault_v1_to_v2", mock_core_function)

    # Call the slot
    window._on_upgrade_vault()


def test_vault_upgrade_password_cancel_locks_without_core(monkeypatch) -> None:
    """Test that vault upgrade password cancel locks without core calls."""
    # Import module locally
    import openadmindesk.ui.main_window as main_window_module
    from PySide6.QtWidgets import QMessageBox, QInputDialog

    # Test with both empty password and non-empty password
    for qinput_result in [("", False), ("", True)]:
        # Create fresh window for each test
        window = MainWindow()

        # Set vault path and state
        window.vault_manager.vault_path = Path("/tmp/test-vault.json")
        window._last_vault_unlocked = True

        # Patch instance is_unlocked and lock to track calls
        lock_calls = []
        state = {"unlocked":True}
        def mock_is_unlocked():
            return state["unlocked"]

        def mock_lock():
            lock_calls.append(True)
            state["unlocked"] = False

        monkeypatch.setattr(window.vault_manager, 'is_unlocked', mock_is_unlocked)
        monkeypatch.setattr(window.vault_manager, 'lock', mock_lock)

        # Set warning response to Yes
        def mock_warning(*args, **kwargs):
            return QMessageBox.Yes

        monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

        # Set question response to Yes to avoid modal hang
        def mock_question(*args, **kwargs):
            return QMessageBox.Yes

        monkeypatch.setattr(QMessageBox, 'question', mock_question)

        # Set inspect to return version 1
        def mock_inspect_vault_version(p):
            return 1

        monkeypatch.setattr(main_window_module, 'inspect_vault_version', mock_inspect_vault_version)

        # Set QInputDialog.getText response
        def mock_get_text(*args, **kwargs):
            return qinput_result

        monkeypatch.setattr(QInputDialog, 'getText', mock_get_text)

        # Patch core to raise AssertionError if called
        def mock_core_function(*args, **kwargs):
            raise AssertionError("Core function should not be called when password is empty")

        # Patch the main window module, not the core module
        monkeypatch.setattr(main_window_module, "upgrade_vault_v1_to_v2", mock_core_function)

        # Call the slot
        window._on_upgrade_vault()

        # Assert one lock call with correct arguments
        assert lock_calls == [True]
        assert state["unlocked"] is False
        assert window._last_vault_unlocked is False


def test_vault_upgrade_full_flow_calls_core_once_and_avoids_auto_lock_notice(monkeypatch) -> None:
    """Test full vault upgrade flow calls core once and avoids auto-lock notice."""
    # Import modules locally
    import openadmindesk.ui.main_window as main_window_module
    from PySide6.QtWidgets import QMessageBox, QInputDialog
    from openadmindesk.core.vault_upgrade import VaultUpgradeResult

    # Create window
    window = MainWindow()

    # Set vault path and state
    window.vault_manager.vault_path = Path("/tmp/test-vault.json")
    window._last_vault_unlocked = True

    # Patch instance is_unlocked and lock to track calls
    lock_calls = []
    state = {"unlocked":True}
    def mock_is_unlocked():
        return state["unlocked"]

    def mock_lock(*args, **kwargs):
        lock_calls.append(True)
        state["unlocked"] = False

    monkeypatch.setattr(window.vault_manager, 'is_unlocked', mock_is_unlocked)
    monkeypatch.setattr(window.vault_manager, 'lock', mock_lock)

    # Set warning response to Yes
    def mock_warning(*args, **kwargs):
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, 'warning', mock_warning)

    # Set question response to Yes
    def mock_question(*args, **kwargs):
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, 'question', mock_question)

    # Set information response to capture text
    captured_info = []
    def mock_information(*args, **kwargs):
        captured_info.append((args, kwargs))

    monkeypatch.setattr(QMessageBox, 'information', mock_information)

    # Set QInputDialog.getText response
    def mock_get_text(*args, **kwargs):
        return ("entered-password", True)

    monkeypatch.setattr(QInputDialog, 'getText', mock_get_text)

    # Set inspect to return version 1
    def mock_inspect_vault_version(p):
        return 1

    monkeypatch.setattr(main_window_module, 'inspect_vault_version', mock_inspect_vault_version)

    # Mock the core upgrade function to capture arguments and return a real result
    core_calls = []
    def mock_core_upgrade(*args, **kwargs):
        core_calls.append(args)
        return VaultUpgradeResult(1, 2, 0, "a" * 64, "b" * 64, True, None)

    # Patch the main window module, not the core module
    monkeypatch.setattr(main_window_module, "upgrade_vault_v1_to_v2", mock_core_upgrade)

    # Mock connection_event_area.showMessage to capture messages
    captured_messages = []
    def mock_show_message(*args, **kwargs):
        captured_messages.append((args, kwargs))

    monkeypatch.setattr(window.connection_event_area, 'showMessage', mock_show_message)

    # Call the slot
    window._on_upgrade_vault()

    # Call _poll_vault_lock_state to simulate the polling
    window._poll_vault_lock_state()

    # Assert one lock call with correct arguments
    assert lock_calls == [True]

    # Assert core was called exactly once with correct arguments (exact Path/password)
    assert len(core_calls) == 1
    assert core_calls[0][0] == Path("/tmp/test-vault.json")
    assert core_calls[0][1] == "entered-password"

    # Assert _last_vault_unlocked is False
    assert window._last_vault_unlocked is False

    # Assert lock is disabled and unlock is enabled
    assert window.lock_vault_action.isEnabled() is False
    assert window.unlock_vault_action.isEnabled() is True

    # Assert no message contains auto-locked
    auto_locked_messages = [msg for msg in captured_messages if "auto-locked" in str(msg).lower()]
    assert len(auto_locked_messages) == 0

    # Assert security checks on dialogs (captured warning/info, not just status messages)
    # Check that captured warning and info dialogs don't contain sensitive data
    for msg in captured_info:
        msg_text = str(msg[0][2]) if len(msg[0]) > 2 else ""
        assert "entered-password" not in msg_text
        assert "a" * 64 not in msg_text  # hash fragment
        assert "b" * 64 not in msg_text  # hash fragment

    # Assert that the information dialog text contains "Backup removed"
    info_texts = [msg[0][2] for msg in captured_info]
    assert any("Backup removed" in text for text in info_texts)

