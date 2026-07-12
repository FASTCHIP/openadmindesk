"""Tests for vault format."""

from openadmindesk.core.vault_format import VaultFormat


def test_vault_format_creation() -> None:
    """Test vault format creation."""
    vault = VaultFormat.create_empty_vault()
    assert vault is not None
    assert vault["version"] == VaultFormat.VERSION
    assert "salt" in vault
    assert "iv" in vault
    assert "ciphertext" in vault
    assert "accounts" in vault


def test_vault_format_validation() -> None:
    """Test vault format validation."""
    # Valid vault
    valid_vault = VaultFormat.create_empty_vault()
    assert VaultFormat.validate_vault_format(valid_vault)
    
    # Invalid vault - missing fields
    invalid_vault = {"version": "1.0", "salt": "test"}
    assert not VaultFormat.validate_vault_format(invalid_vault)


def test_vault_format_serialization() -> None:
    """Test vault format serialization."""
    vault = VaultFormat.create_empty_vault()
    
    # Serialize
    json_str = VaultFormat.serialize_vault(vault)
    assert json_str is not None
    
    # Deserialize
    restored_vault = VaultFormat.deserialize_vault(json_str)
    assert restored_vault is not None
    assert restored_vault["version"] == VaultFormat.VERSION

def test_vault_format_rejects_unsupported_version() -> None:
    """Vault format validation should reject unknown schema versions."""
    vault = VaultFormat.create_empty_vault()
    vault["version"] = "999.0"

    assert not VaultFormat.validate_vault_format(vault)


def test_vault_format_requires_accounts_list() -> None:
    """Accounts must stay a list so callers cannot load malformed vault data."""
    vault = VaultFormat.create_empty_vault()
    vault["accounts"] = {}

    assert not VaultFormat.validate_vault_format(vault)
