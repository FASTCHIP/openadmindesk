"""Vault file format specification."""

from __future__ import annotations

from typing import Dict, Any, Optional
import json


# Version constants
LEGACY_VERSION = "1.0"
LATEST_VERSION = 2


def _is_valid_hex_shape(s: str, expected_hex_chars: int) -> bool:
    """Check if a non-empty string is valid hex of the expected length.

    Empty strings are allowed (template compatibility with create_empty_vault).
    Non-empty strings must have exactly expected_hex_chars hex characters.
    """
    if not s:
        return True
    if len(s) != expected_hex_chars:
        return False
    try:
        int(s, 16)
        return True
    except (ValueError, TypeError):
        return False


def detect_version(data: Dict[str, Any]) -> Optional[int]:
    """Detect the vault format version from parsed data.

    Returns 1 for "1.0", 2 for integer 2, or None for unknown/missing.
    """
    version = data.get("version")
    if version == LEGACY_VERSION:
        return 1
    if version == LATEST_VERSION:
        return 2
    return None


def _validate_v1(data: Dict[str, Any]) -> bool:
    """Validate v1 vault structure (LEGACY_VERSION "1.0").

    Required: version (str "1.0"), salt (hex str), key_hash (hex str), accounts (list).
    Optional: iv (str), ciphertext (str) - backward-compatible fields.
    Optional: kdf (str), kdf_params (dict), created_at (str), updated_at (str).
    salt and key_hash should be non-empty hex strings.
    accounts must be a list.
    """
    if not isinstance(data.get("version"), str):
        return False
    if data["version"] != LEGACY_VERSION:
        return False

    # Required fields
    for field in ("salt", "key_hash", "accounts"):
        if field not in data:
            return False

    # Validate accounts is a list
    if not isinstance(data["accounts"], list):
        return False

    # Validate salt and key_hash are strings
    salt = data.get("salt", "")
    key_hash = data.get("key_hash", "")
    if not isinstance(salt, str):
        return False
    if not isinstance(key_hash, str):
        return False

    # When non-empty, validate hex shape for persisted values
    # salt: 32 hex chars (16 bytes), key_hash: 16 hex chars (8 bytes)
    if not _is_valid_hex_shape(salt, 32):
        return False
    if not _is_valid_hex_shape(key_hash, 16):
        return False

    # Optional iv/ciphertext - no validation if absent
    if "iv" in data and not isinstance(data["iv"], str):
        return False
    if "ciphertext" in data and not isinstance(data["ciphertext"], str):
        return False

    # Optional metadata fields - type checks
    if "kdf" in data and not isinstance(data["kdf"], str):
        return False
    if "kdf_params" in data and not isinstance(data["kdf_params"], dict):
        return False
    if "created_at" in data and not isinstance(data["created_at"], str):
        return False
    if "updated_at" in data and not isinstance(data["updated_at"], str):
        return False

    return True


def _validate_v2(data: Dict[str, Any]) -> bool:
    """Validate v2 vault structure (LATEST_VERSION 2).

    Required: version (int 2), salt, kdf (str "argon2id"), kdf_params (dict),
    password_hash (str), accounts (list), created_at (str), updated_at (str).
    No v2 crypto/setup implementation yet.
    """
    if not isinstance(data.get("version"), int):
        return False
    if data["version"] != LATEST_VERSION:
        return False

    for field in ("salt", "kdf", "kdf_params", "password_hash", "accounts",
                  "created_at", "updated_at"):
        if field not in data:
            return False

    if not isinstance(data["accounts"], list):
        return False

    if not isinstance(data.get("kdf"), str) or not data["kdf"]:
        return False

    if not isinstance(data.get("kdf_params"), dict):
        return False

    if not isinstance(data.get("password_hash"), str) or not data["password_hash"]:
        return False

    if not isinstance(data.get("salt"), str) or not data["salt"]:
        return False

    if not isinstance(data.get("created_at"), str) or not data["created_at"]:
        return False

    if not isinstance(data.get("updated_at"), str) or not data["updated_at"]:
        return False

    return True


class VaultFormat:
    """Defines the vault file format."""

    # Vault format version
    VERSION = LEGACY_VERSION

    @staticmethod
    def create_empty_vault() -> Dict[str, Any]:
        """Create an empty vault structure (v1 legacy format)."""
        return {
            "version": LEGACY_VERSION,
            "salt": "",
            "key_hash": "",
            "iv": "",
            "ciphertext": "",
            "accounts": []
        }

    @staticmethod
    def validate_vault_format(data: Dict[str, Any]) -> bool:
        """Validate vault format and supported schema version."""
        version_num = detect_version(data)
        if version_num == 1:
            return _validate_v1(data)
        if version_num == 2:
            return _validate_v2(data)
        return False

    @staticmethod
    def serialize_vault(vault_data: Dict[str, Any]) -> str:
        """Serialize vault data to JSON."""
        return json.dumps(vault_data, indent=2)

    @staticmethod
    def deserialize_vault(json_str: str) -> Dict[str, Any]:
        """Deserialize vault data from JSON."""
        return json.loads(json_str)
