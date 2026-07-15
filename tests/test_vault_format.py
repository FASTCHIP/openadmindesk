"""Tests for vault format."""

from openadmindesk.core.vault_format import (
    VaultFormat,
    detect_version,
    LEGACY_VERSION,
    LATEST_VERSION,
)

# Test helpers
_SALT_32HEX = "abcdef0123456789abcdef0123456789"
_KEYHASH_16HEX = "deadbeef12345678"


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
    invalid_vault = {"version": "1.0", "salt": _SALT_32HEX}
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


# --- New tests for Phase 9.9a ---


def test_detect_version_returns_1_for_legacy() -> None:
    """detect_version returns 1 for '1.0' string version."""
    data = {"version": "1.0"}
    assert detect_version(data) == 1


def test_detect_version_returns_2_for_latest() -> None:
    """detect_version returns 2 for integer version 2."""
    data = {"version": 2}
    assert detect_version(data) == 2


def test_detect_version_returns_none_for_unknown() -> None:
    """detect_version returns None for unknown/missing version."""
    assert detect_version({}) is None
    assert detect_version({"version": "3.0"}) is None
    assert detect_version({"version": None}) is None
    assert detect_version({"version": 99}) is None


def test_v1_accepts_missing_iv_ciphertext() -> None:
    """V1 validation accepts vault without optional iv/ciphertext fields."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert VaultFormat.validate_vault_format(vault)


def test_v1_rejects_missing_key_hash() -> None:
    """V1 validation rejects vault without required key_hash field."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_missing_salt() -> None:
    """V1 validation rejects vault without required salt field."""
    vault = {
        "version": "1.0",
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_missing_accounts() -> None:
    """V1 validation rejects vault without required accounts field."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_salt() -> None:
    """V1 validation rejects non-string salt."""
    vault = {
        "version": "1.0",
        "salt": 12345,
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_key_hash() -> None:
    """V1 validation rejects non-string key_hash."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": 12345,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_list_accounts() -> None:
    """V1 validation rejects non-list accounts."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": "not_a_list"
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_iv() -> None:
    """V1 validation rejects non-string iv if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "iv": 123,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_ciphertext() -> None:
    """V1 validation rejects non-string ciphertext if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "ciphertext": 456,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_accepts_optional_metadata() -> None:
    """V1 validation accepts vault with optional kdf/kdf_params/timestamps."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "kdf": "pbkdf2-sha256",
        "kdf_params": {"iterations": 100000, "length": 32},
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z"
    }
    assert VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_kdf() -> None:
    """V1 validation rejects non-string kdf if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "kdf": 123
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_dict_kdf_params() -> None:
    """V1 validation rejects non-dict kdf_params if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "kdf_params": "not_a_dict"
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_created_at() -> None:
    """V1 validation rejects non-string created_at if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "created_at": 12345
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_non_string_updated_at() -> None:
    """V1 validation rejects non-string updated_at if present."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "updated_at": 12345
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v2_structural_validation() -> None:
    """V2 structural validation accepts complete v2 vault structure.

    Note: no v2 crypto/setup is implemented yet. This verifies the
    structural placeholder definition only.
    """
    vault = {
        "version": 2,
        "salt": _SALT_32HEX,
        "kdf": "argon2id",
        "kdf_params": {"time_cost": 2, "memory_cost": 19456, "parallelism": 1},
        "password_hash": "abcdef1234567890abcdef1234567890",
        "accounts": [],
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z"
    }
    assert VaultFormat.validate_vault_format(vault)


def test_v2_rejects_missing_fields() -> None:
    """V2 validation rejects vault with missing required fields."""
    vault = {"version": 2, "salt": "test"}
    assert not VaultFormat.validate_vault_format(vault)


def test_v2_rejects_wrong_version_type() -> None:
    """V2 validation rejects wrong version type (string instead of int)."""
    vault = {
        "version": "2",
        "salt": _SALT_32HEX,
        "kdf": "argon2id",
        "kdf_params": {},
        "password_hash": "hash",
        "accounts": [],
        "created_at": "t",
        "updated_at": "t"
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v2_rejects_non_list_accounts() -> None:
    """V2 validation rejects non-list accounts."""
    vault = {
        "version": 2,
        "salt": _SALT_32HEX,
        "kdf": "argon2id",
        "kdf_params": {},
        "password_hash": "hash",
        "accounts": "not_a_list",
        "created_at": "t",
        "updated_at": "t"
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v2_rejects_missing_password_hash() -> None:
    """V2 validation rejects vault without password_hash."""
    vault = {
        "version": 2,
        "salt": _SALT_32HEX,
        "kdf": "argon2id",
        "kdf_params": {},
        "accounts": [],
        "created_at": "t",
        "updated_at": "t"
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_consecutive_salt_key_hash_empty_allowed() -> None:
    """Empty salt and key_hash in template are valid (create_empty_vault compat)."""
    vault = VaultFormat.create_empty_vault()
    assert vault["salt"] == ""
    assert vault["key_hash"] == ""
    assert VaultFormat.validate_vault_format(vault)


def test_legacy_version_constant() -> None:
    """LEGACY_VERSION equals '1.0'."""
    assert LEGACY_VERSION == "1.0"


def test_latest_version_constant() -> None:
    """LATEST_VERSION equals 2."""
    assert LATEST_VERSION == 2


def test_serialization_roundtrip_with_metadata() -> None:
    """Serialize and deserialize preserves metadata fields."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": _KEYHASH_16HEX,
        "accounts": [],
        "kdf": "pbkdf2-sha256",
        "kdf_params": {"iterations": 100000, "length": 32},
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z"
    }
    json_str = VaultFormat.serialize_vault(vault)
    restored = VaultFormat.deserialize_vault(json_str)
    assert restored["kdf"] == "pbkdf2-sha256"
    assert restored["kdf_params"]["iterations"] == 100000
    assert restored["created_at"] == "2026-07-15T12:00:00Z"
    assert restored["updated_at"] == "2026-07-15T12:00:00Z"
    assert VaultFormat.validate_vault_format(restored)


# --- Hex shape validation tests ---


def test_v1_accepts_valid_salt_various_hex() -> None:
    """V1 accepts valid 32-char hex salt with various hex digits."""
    vault = {
        "version": "1.0",
        "salt": "0123456789abcdef0123456789abcdef",
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert VaultFormat.validate_vault_format(vault)


def test_v1_accepts_valid_key_hash_various_hex() -> None:
    """V1 accepts valid 16-char hex key_hash with various hex digits."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": "0123456789abcdef",
        "accounts": []
    }
    assert VaultFormat.validate_vault_format(vault)


def test_v1_rejects_salt_wrong_length_short() -> None:
    """V1 rejects salt that is non-empty but wrong (short) hex length."""
    vault = {
        "version": "1.0",
        "salt": "abcdef01",  # too short, 8 chars
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_salt_wrong_length_long() -> None:
    """V1 rejects salt that is non-empty but wrong (long) hex length."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX + "ff",  # too long, 34 chars
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_key_hash_wrong_length() -> None:
    """V1 rejects key_hash that is non-empty but wrong hex length."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": "abcdef01",  # too short, 8 chars
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_salt_non_hex_chars() -> None:
    """V1 rejects salt with non-hex characters when non-empty."""
    vault = {
        "version": "1.0",
        "salt": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",  # 32 non-hex chars
        "key_hash": _KEYHASH_16HEX,
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)


def test_v1_rejects_key_hash_non_hex_chars() -> None:
    """V1 rejects key_hash with non-hex characters when non-empty."""
    vault = {
        "version": "1.0",
        "salt": _SALT_32HEX,
        "key_hash": "zzzzzzzzzzzzzzzz",  # 16 non-hex chars
        "accounts": []
    }
    assert not VaultFormat.validate_vault_format(vault)
