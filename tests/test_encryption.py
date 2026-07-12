"""Tests for encryption."""

import tempfile
import os
from openadmindesk.core.vault_manager import VaultManager


def test_encryption_decryption() -> None:
    """Test encryption and decryption."""
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        vault_path = tmp.name
    
    try:
        manager = VaultManager(vault_path)
        
        # Setup master password
        success = manager.setup_master_password("testpassword123")
        assert success
        
        # Unlock
        unlocked = manager.unlock("testpassword123")
        assert unlocked
        
        # Test encryption/decryption
        test_data = "This is secret data"
        
        # Encrypt
        iv, ciphertext = manager._encrypt_data(test_data)
        assert iv is not None
        assert ciphertext is not None
        
        # Decrypt
        decrypted = manager._decrypt_data(iv, ciphertext)
        assert decrypted == test_data
        
    finally:
        # Clean up
        if os.path.exists(vault_path):
            os.unlink(vault_path)