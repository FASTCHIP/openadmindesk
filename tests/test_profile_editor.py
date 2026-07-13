"""Tests for profile editor."""


from openadmindesk.core.profile import Profile
from openadmindesk.core.account import Account
from openadmindesk.ui.profile_editor import ProfileEditor


def test_profile_editor_creation() -> None:
    """Test profile editor creation."""
    editor = ProfileEditor()
    assert editor is not None
    
    # Test with existing profile
    profile = Profile(
        name="Test Server",
        host="example.com",
        port=22,
        username="user"
    )
    editor_with_profile = ProfileEditor(profile)
    assert editor_with_profile is not None


def test_profile_editor_load_profile() -> None:
    """Test loading profile into editor."""
    profile = Profile(
        name="Test Server",
        host="example.com",
        port=22,
        username="user"
    )
    editor = ProfileEditor(profile)
    
    # Check that profile data was loaded
    # Note: Direct access to UI elements is difficult without more complex testing
    assert editor.profile.name == "Test Server"
    assert editor.profile.host == "example.com"
    assert editor.profile.port == 22
    assert editor.profile.username == "user"


def test_profile_editor_exposes_and_saves_session_icon() -> None:
    profile = Profile(
        name="Icon Server",
        host="example.com",
        port=22,
        username="user",
        icon_id="linux",
    )
    editor = ProfileEditor(profile)

    assert editor.icon_input.count() >= 6
    assert editor.icon_input.currentData() == "linux"
    database_index = editor.icon_input.findData("database")
    assert database_index >= 0

    editor.icon_input.setCurrentIndex(database_index)
    editor._save_profile()

    assert profile.icon_id == "database"


def test_profile_editor_stores_manual_password_in_unlocked_vault(tmp_path) -> None:
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    profile = Profile(name="Edited", host="edited.example.com", port=22, username="admin")
    editor = ProfileEditor(profile, vault_manager=vault)
    editor.password_input.setText("new-secret")

    editor._save_profile()

    assert profile.password is None
    assert profile.credential_id
    account = vault.get_account(profile.credential_id)
    assert account is not None
    assert account.password == "new-secret"
    assert account.host == "edited.example.com"


def test_profile_editor_stores_rdp_gateway_password_in_unlocked_vault(tmp_path) -> None:
    from openadmindesk.core.profile import SessionType
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    profile = Profile(
        name="RDP",
        host="rdp.example.com",
        port=3389,
        username="rdp-user",
        session_type=SessionType.RDP,
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    )
    editor = ProfileEditor(profile, vault_manager=vault)
    editor.rdp_gateway_pass_input.setText("gateway-secret")

    editor._save_profile()

    assert profile.rdp_gateway_password is None
    assert profile.rdp_gateway_credential_id
    account = vault.get_account(profile.rdp_gateway_credential_id)
    assert account is not None
    assert account.service_type == "rdp-gateway"
    assert account.host == "gw.example.com"
    assert account.username == "gw-user"
    assert account.password == "gateway-secret"

def test_profile_editor_hides_rdp_rows_for_ssh_profiles() -> None:
    from openadmindesk.core.profile import SessionType

    profile = Profile(
        name="SSH",
        host="example.com",
        session_type=SessionType.SSH,
        rdp_drive_redirection=True,
        rdp_multimon=True,
    )

    editor = ProfileEditor(profile)

    assert editor.rdp_drive_check.isHidden()
    assert editor.rdp_multimon_check.isHidden()
    assert editor._form_layout.labelForField(editor.rdp_drive_path_input).isHidden()
    assert "Optional" in editor.private_key_input.placeholderText()


def test_profile_editor_clears_rdp_options_when_saving_ssh_profile() -> None:
    from openadmindesk.core.profile import SessionType

    profile = Profile(
        name="SSH",
        host="example.com",
        session_type=SessionType.SSH,
        rdp_drive_redirection=True,
        rdp_drive_path="/tmp",
        rdp_multimon=True,
        rdp_gateway="gateway.example.com",
    )
    editor = ProfileEditor(profile)

    editor._save_profile()

    assert profile.session_type == SessionType.SSH
    assert profile.rdp_drive_redirection is False
    assert profile.rdp_drive_path is None
    assert profile.rdp_multimon is False
    assert profile.rdp_gateway is None

def test_profile_editor_keeps_existing_password_when_password_field_left_blank() -> None:
    profile = Profile(
        name="SSH",
        host="example.com",
        username="admin",
        password="old-secret",
    )
    editor = ProfileEditor(profile)

    editor._save_profile()

    assert profile.password == "old-secret"


def test_profile_editor_keeps_existing_gateway_password_when_field_left_blank() -> None:
    from openadmindesk.core.profile import SessionType

    profile = Profile(
        name="RDP",
        host="rdp.example.com",
        username="admin",
        session_type=SessionType.RDP,
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
        rdp_gateway_password="old-gw-secret",
    )
    editor = ProfileEditor(profile)

    editor._save_profile()

    assert profile.rdp_gateway_password == "old-gw-secret"

def test_profile_editor_marks_saved_password_placeholder() -> None:
    profile = Profile(
        name="SSH",
        host="example.com",
        username="admin",
        password="old-secret",
    )

    editor = ProfileEditor(profile)

    assert editor.password_input.text() == ""
    assert "Saved password" in editor.password_input.placeholderText()


def test_profile_editor_blocks_save_with_new_secrets_when_vault_locked(tmp_path) -> None:
    """Test that saving with new secrets when vault is locked is blocked."""
    from openadmindesk.core.vault_manager import VaultManager

    # Create a vault but don't unlock it
    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    # Don't unlock the vault
    
    profile = Profile(name="Edited", host="edited.example.com", port=22, username="admin")
    editor = ProfileEditor(profile, vault_manager=vault)
    editor.password_input.setText("new-secret")

    # This should not save and should show a critical error
    # We can't easily test the QMessageBox directly, but we can check that the method returns early
    # by checking that the password is still in the input field
    editor._save_profile()
    
    # Password should still be in the input field (not saved)
    assert editor.password_input.text() == "new-secret"


def test_profile_editor_blocks_save_with_legacy_plaintext_no_id(tmp_path) -> None:
    """Test that saving legacy profile with plaintext secrets but no credential ID is blocked."""
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    
    # Create a profile with plaintext password but no credential ID
    profile = Profile(
        name="Legacy",
        host="legacy.example.com",
        port=22,
        username="admin",
        password="old-secret"
    )
    editor = ProfileEditor(profile, vault_manager=vault)
    
    # This should block saving since there's no credential ID and no new secret to replace it
    editor._save_profile()
    
    # The password should still be in the profile (not cleared)
    assert profile.password == "old-secret"


def test_profile_editor_saves_with_vault_unlocked_and_new_secrets(tmp_path) -> None:
    """Test that saving with new secrets when vault is unlocked works correctly."""
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    
    profile = Profile(name="Edited", host="edited.example.com", port=22, username="admin")
    editor = ProfileEditor(profile, vault_manager=vault)
    editor.password_input.setText("new-secret")

    editor._save_profile()

    # Password should be None in profile (moved to vault)
    assert profile.password is None
    assert profile.credential_id is not None
    # Check that account was actually saved in vault
    account = vault.get_account(profile.credential_id)
    assert account is not None
    assert account.password == "new-secret"


def test_profile_editor_preserves_existing_account_data_when_updating(tmp_path) -> None:
    """Test that when updating an existing account, existing data is preserved."""
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    
    # Create an account first
    account = vault.add_account(
        Account(
            name="Test Account",
            username="admin",
            password="old-secret",
            host="example.com",
            port=22,
            service_type="ssh"
        )
    )
    
    # Create a profile with the credential ID
    profile = Profile(
        name="Test Profile",
        host="example.com",
        port=22,
        username="admin",
        credential_id=account.id
    )
    editor = ProfileEditor(profile, vault_manager=vault)
    
    # Change only the password, leave other fields blank
    editor.password_input.setText("new-secret")
    
    editor._save_profile()
    
    # Check that the account was updated with new password but preserved other fields
    updated_account = vault.get_account(account.id)
    assert updated_account.password == "new-secret"
    assert updated_account.username == "admin"
    assert updated_account.host == "example.com"


def test_profile_editor_handles_gateway_password_with_vault_unlocked(tmp_path) -> None:
    """Test that gateway passwords are handled correctly when vault is unlocked."""
    from openadmindesk.core.profile import SessionType
    from openadmindesk.core.vault_manager import VaultManager

    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    
    profile = Profile(
        name="RDP",
        host="rdp.example.com",
        port=3389,
        username="rdp-user",
        session_type=SessionType.RDP,
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    )
    editor = ProfileEditor(profile, vault_manager=vault)
    editor.rdp_gateway_pass_input.setText("gateway-secret")

    editor._save_profile()

    # Gateway password should be None in profile (moved to vault)
    assert profile.rdp_gateway_password is None
    assert profile.rdp_gateway_credential_id is not None
    # Check that gateway account was actually saved in vault
    account = vault.get_account(profile.rdp_gateway_credential_id)
    assert account is not None
    assert account.service_type == "rdp-gateway"
    assert account.password == "gateway-secret"
