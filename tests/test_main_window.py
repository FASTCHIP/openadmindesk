"""Test for main window."""


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


def test_main_window_applies_terminal_settings_to_open_ssh_tabs() -> None:
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

