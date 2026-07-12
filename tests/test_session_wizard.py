"""Tests for session creation wizard."""

from __future__ import annotations

from openadmindesk.core.profile import SessionType
from openadmindesk.core.profile_store import Folder, ProfileStore
from openadmindesk.ui.session_wizard import SessionWizard


def test_session_wizard_protocol_page_supports_every_session_type(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    for session_type in SessionType:
        wizard.protocol_page._select(session_type)
        assert wizard.protocol_page.selected_type() == session_type


def test_session_wizard_defaults_ports_for_supported_types(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    expected_ports = {
        SessionType.SSH: 22,
        SessionType.RDP: 3389,
        SessionType.TELNET: 23,
        SessionType.LOCAL_SHELL: 1,
        SessionType.VNC: 5900,
    }
    for session_type, expected_port in expected_ports.items():
        wizard.protocol_page._select(session_type)
        wizard.connection_page.initializePage()
        assert wizard.connection_page.port_input.value() == expected_port


def test_session_wizard_build_profile_saves_selected_folder(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    assert store.save_folder(Folder("Production"))
    wizard = SessionWizard(store)

    wizard.protocol_page._select(SessionType.SSH)
    wizard.connection_page.name_input.setText("Prod SSH")
    wizard.connection_page.host_input.setText("prod.example.com")
    wizard.connection_page.port_input.setValue(22)
    wizard.connection_page.folder_combo.setCurrentIndex(1)
    wizard.credential_page.username_input.setText("admin")

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.session_type == SessionType.SSH
    assert profile.parent_folder == "Production"
    assert profile.username == "admin"



def test_session_wizard_stores_manual_password_in_unlocked_vault(tmp_path) -> None:
    from openadmindesk.core.vault_manager import VaultManager

    store = ProfileStore(str(tmp_path / "profiles.db"))
    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    wizard = SessionWizard(store, vault=vault)

    wizard.protocol_page._select(SessionType.SSH)
    wizard.connection_page.name_input.setText("Vault SSH")
    wizard.connection_page.host_input.setText("vault.example.com")
    wizard.connection_page.port_input.setValue(22)
    wizard.credential_page.username_input.setText("admin")
    wizard.credential_page.password_input.setText("top-secret")

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.password is None
    assert profile.credential_id
    account = vault.get_account(profile.credential_id)
    assert account is not None
    assert account.password == "top-secret"
    assert account.username == "admin"

def test_session_wizard_protocol_grid_shows_planned_disabled_protocols(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    planned = ["sftp", "ftp", "serial", "browser", "mosh"]
    for key in planned:
        assert key in wizard.protocol_page._option_buttons
        assert not wizard.protocol_page._option_buttons[key].isEnabled()


def test_session_wizard_applies_protocol_template(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    wizard.protocol_page._select(SessionType.RDP)
    wizard.connection_page.initializePage()
    wizard.connection_page.template_combo.setCurrentIndex(1)

    assert wizard.connection_page.name_input.text() == "Windows Desktop"
    assert wizard.connection_page.host_input.text() == "windows.example.com"
    assert wizard.connection_page.port_input.value() == 3389
    assert wizard.credential_page.username_input.text() == "Administrator"
    assert "windows.example.com:3389" in wizard.connection_page.summary_label.text()


def test_session_wizard_temporary_connect_does_not_save_profile(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    wizard.protocol_page._select(SessionType.SSH)
    wizard.connection_page.name_input.setText("Temporary SSH")
    wizard.connection_page.host_input.setText("temp.example.com")
    wizard.connection_page.port_input.setValue(22)
    wizard.credential_page.username_input.setText("admin")
    wizard.credential_page.launch_combo.setCurrentIndex(2)

    wizard.accept()

    assert wizard.connect_after()
    assert wizard.created_profile() is not None
    assert store.load_all_profiles() == []


# ── Advanced fields tests ────────────────────────────────────────────────────


def _setup_basic_ssh(wizard, name="Test SSH", host="test.example.com") -> None:
    """Helper: fill basic SSH fields."""
    wizard.protocol_page._select(SessionType.SSH)
    wizard.connection_page.name_input.setText(name)
    wizard.connection_page.host_input.setText(host)
    wizard.connection_page.port_input.setValue(22)


def test_ssh_advanced_fields_persist_to_profile(tmp_path) -> None:
    """SSH advanced options (agent, compression, keepalive, X11, proxy) persist."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    _setup_basic_ssh(wizard)
    wizard.credential_page.username_input.setText("admin")

    # Fill SSH advanced page
    wizard.ssh_advanced_page.agent_cb.setChecked(True)
    wizard.ssh_advanced_page.compression_cb.setChecked(True)
    wizard.ssh_advanced_page.keepalive_cb.setChecked(True)
    wizard.ssh_advanced_page.x11_cb.setChecked(True)
    wizard.ssh_advanced_page.proxy_input.setText("ssh -W %h:%p jump.example.com")

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.use_ssh_agent is True
    assert profile.compression is True
    assert profile.keep_alive is True
    assert profile.x11_forwarding is True
    assert profile.proxy_command == "ssh -W %h:%p jump.example.com"
    # No plaintext password in profile
    assert profile.password is None


def test_ssh_advanced_fields_default_to_false(tmp_path) -> None:
    """SSH advanced options default to sensible values when not set."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    _setup_basic_ssh(wizard)
    wizard.credential_page.username_input.setText("admin")

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.use_ssh_agent is False
    assert profile.compression is False
    assert profile.keep_alive is True   # default in Profile model
    assert profile.x11_forwarding is False
    assert profile.proxy_command is None
    assert profile.password is None


def test_rdp_advanced_fields_persist_to_profile(tmp_path) -> None:
    """RDP advanced options persist."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    wizard.protocol_page._select(SessionType.RDP)
    wizard.connection_page.name_input.setText("Test RDP")
    wizard.connection_page.host_input.setText("rdp.example.com")
    wizard.connection_page.port_input.setValue(3389)
    wizard.credential_page.username_input.setText("admin")

    # Fill RDP advanced page
    wizard.rdp_advanced_page.gateway_input.setText("gw.example.com")
    wizard.rdp_advanced_page.gateway_user_input.setText("gwuser")
    wizard.rdp_advanced_page.cert_combo.setCurrentIndex(2)  # ignore
    wizard.rdp_advanced_page.drive_cb.setChecked(True)
    wizard.rdp_advanced_page.drive_path_input.setText("/mnt/share")
    wizard.rdp_advanced_page.printer_cb.setChecked(True)
    wizard.rdp_advanced_page.clipboard_cb.setChecked(False)
    wizard.rdp_advanced_page.multimon_cb.setChecked(True)

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.rdp_gateway == "gw.example.com"
    assert profile.rdp_gateway_username == "gwuser"
    assert profile.rdp_certificate_policy == "ignore"
    assert profile.rdp_drive_redirection is True
    assert profile.rdp_drive_path == "/mnt/share"
    assert profile.rdp_printer_redirection is True
    assert profile.rdp_clipboard_redirection is False
    assert profile.rdp_multimon is True
    assert profile.password is None


def test_vnc_advanced_fields_persist_to_profile(tmp_path) -> None:
    """VNC advanced options persist."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    wizard.protocol_page._select(SessionType.VNC)
    wizard.connection_page.name_input.setText("Test VNC")
    wizard.connection_page.host_input.setText("vnc.example.com")
    wizard.connection_page.port_input.setValue(5900)

    # Fill VNC advanced page
    wizard.vnc_advanced_page.scaling_cb.setChecked(True)
    wizard.vnc_advanced_page.viewonly_cb.setChecked(True)
    wizard.vnc_advanced_page.color_combo.setCurrentIndex(0)  # 8-bit

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.vnc_scaling is True
    assert profile.vnc_view_only is True
    assert profile.vnc_color_depth == 8
    assert profile.password is None


def test_notes_persist_to_profile(tmp_path) -> None:
    """Session notes from summary page persist."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    wizard = SessionWizard(store)

    _setup_basic_ssh(wizard)
    wizard.credential_page.username_input.setText("admin")

    # Set notes (summary page field)
    wizard.summary_page.notes_input.setText("My important note")

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.notes == "My important note"


def test_no_plaintext_password_in_profile_when_vault_used(tmp_path) -> None:
    """Password goes to vault, not profile, when vault is unlocked."""
    from openadmindesk.core.vault_manager import VaultManager

    store = ProfileStore(str(tmp_path / "profiles.db"))
    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret")
    assert vault.unlock("secret")
    wizard = SessionWizard(store, vault=vault)

    _setup_basic_ssh(wizard, name="NoPlaintext", host="pt.example.com")
    wizard.credential_page.username_input.setText("admin")
    wizard.credential_page.password_input.setText("secret-password")

    # Advanced fields don't affect vault behaviour
    wizard.ssh_advanced_page.agent_cb.setChecked(True)

    profile = wizard._build_profile()

    assert profile is not None
    assert profile.password is None  # never stored in profile
    assert profile.credential_id is not None
    # Advanced fields still present
    assert profile.use_ssh_agent is True

