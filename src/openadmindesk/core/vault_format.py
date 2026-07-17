"""Vault file format specification."""

from __future__ import annotations

from typing import Dict, Any, Optional
import json


# Version constants
LEGACY_VERSION = "1.0"
LATEST_VERSION = 2

# Required kdf_params keys for v2 vaults
_REQUIRED_V2_KDF_KEYS = frozenset({
    "time_cost", "memory_cost", "parallelism", "hash_len", "version"
})


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

    Required: version (int 2), salt (hex str 32 chars, empty allowed template),
    kdf (str exactly "argon2id"), kdf_params (dict with int-not-bool values),
    password_hash (hex str 64 chars, empty allowed template),
    accounts (list), created_at (str), updated_at (str).
    No iv/ciphertext/key_hash fields in v2.
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

    # kdf must be exactly "argon2id"
    kdf = data.get("kdf")
    if not isinstance(kdf, str) or kdf != "argon2id":
        return False

    # kdf_params must have exactly the required keys (time_cost, memory_cost,
    # parallelism, hash_len, version); each value must be int (not bool)
    kdf_params = data.get("kdf_params")
    if not isinstance(kdf_params, dict):
        return False
    if set(kdf_params.keys()) != _REQUIRED_V2_KDF_KEYS:
        return False
    for val in kdf_params.values():
        if isinstance(val, bool) or not isinstance(val, int):
            return False

    # salt: empty allowed (template), otherwise exactly 32 hex chars
    salt = data.get("salt")
    if not isinstance(salt, str):
        return False
    if salt and not _is_valid_hex_shape(salt, 32):
        return False

    # password_hash: empty allowed (template), otherwise exactly 64 hex chars
    password_hash = data.get("password_hash")
    if not isinstance(password_hash, str):
        return False
    if password_hash and not _is_valid_hex_shape(password_hash, 64):
        return False

    # created_at and updated_at must be strings (empty template allowed)
    if not isinstance(data.get("created_at"), str):
        return False
    if not isinstance(data.get("updated_at"), str):
        return False

    # No legacy v1 fields in v2
    for legacy_field in ("iv", "ciphertext", "key_hash"):
        if legacy_field in data:
            return False

    return True


class VaultFormat:
    """Defines the vault file format."""

    # Vault format version (default is latest)
    VERSION = LATEST_VERSION

    @staticmethod
    def create_empty_vault(version: int = LATEST_VERSION) -> Dict[str, Any]:
        """Create an empty vault structure.

        Args:
            version: The vault format version to produce.
                     LATEST_VERSION (2) produces a v2 argon2id template.
                     LEGACY_VERSION ("1.0") produces the old v1 PBKDF2 template.

        Returns:
            Dict suitable for serialization.
        """
        if version == 1 or version == LEGACY_VERSION:
            return {
                "version": LEGACY_VERSION,
                "salt": "",
                "key_hash": "",
                "iv": "",
                "ciphertext": "",
                "accounts": []
            }
        # Default: v2 template
        return {
            "version": LATEST_VERSION,
            "salt": "",
            "kdf": "argon2id",
            "kdf_params": {
                "time_cost": 2,
                "memory_cost": 19456,
                "parallelism": 1,
                "hash_len": 32,
                "version": 19,
            },
            "password_hash": "",
            "accounts": [],
            "created_at": "",
            "updated_at": ""
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
