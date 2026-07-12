"""Vault file format specification."""

from __future__ import annotations

from typing import Dict, Any, List
import json


class VaultFormat:
    """Defines the vault file format."""
    
    # Vault format version
    VERSION = "1.0"
    
    # Vault structure
    SCHEMA = {
        "version": str,
        "salt": str,
        "iv": str,
        "ciphertext": str,
        "accounts": List[Dict[str, Any]]
    }
    
    @staticmethod
    def create_empty_vault() -> Dict[str, Any]:
        """Create an empty vault structure."""
        return {
            "version": VaultFormat.VERSION,
            "salt": "",
            "key_hash": "",
            "iv": "",
            "ciphertext": "",
            "accounts": []
        }
    
    @staticmethod
    def validate_vault_format(data: Dict[str, Any]) -> bool:
        """Validate vault format and supported schema version."""
        required_fields = ["version", "salt", "iv", "ciphertext", "accounts"]
        for field in required_fields:
            if field not in data:
                return False
        if data["version"] != VaultFormat.VERSION:
            return False
        if not isinstance(data["accounts"], list):
            return False
        return True
    
    @staticmethod
    def serialize_vault(vault_data: Dict[str, Any]) -> str:
        """Serialize vault data to JSON."""
        return json.dumps(vault_data, indent=2)
    
    @staticmethod
    def deserialize_vault(json_str: str) -> Dict[str, Any]:
        """Deserialize vault data from JSON."""
        return json.loads(json_str)