"""Tests for sync manager."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openadmindesk.core.sync_manager import SyncManager
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.vault_manager import VaultManager


def test_sync_manager_creation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "profiles.db")
        vault_path = str(Path(tmpdir) / "vault.json")
        store = ProfileStore(db)
        vault = VaultManager(vault_path)
        sm = SyncManager(store, vault)
        assert sm.config.enabled is False
        assert sm.config.sync_folder == ""


def test_sync_configure() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "profiles.db")
        vault_path = str(Path(tmpdir) / "vault.json")
        store = ProfileStore(db)
        vault = VaultManager(vault_path)
        sm = SyncManager(store, vault)
        sm.configure(tmpdir, "test_password_123", "merge")
        assert sm.config.enabled is True
        assert sm.config.sync_folder == tmpdir
        assert sm.config.conflict_mode == "merge"
        assert sm.config.sync_password_hash != ""


def test_sync_encrypt_decrypt() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "profiles.db")
        vault_path = str(Path(tmpdir) / "vault.json")
        store = ProfileStore(db)
        vault = VaultManager(vault_path)
        sm = SyncManager(store, vault)
        plaintext = "hello world test data"
        encrypted = sm._encrypt(plaintext, "password123")
        assert encrypted != plaintext
        decrypted = sm._decrypt(encrypted, "password123")
        assert decrypted == plaintext
        assert sm._decrypt(encrypted, "wrongpassword") is None


def test_sync_disable() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "profiles.db")
        vault_path = str(Path(tmpdir) / "vault.json")
        store = ProfileStore(db)
        vault = VaultManager(vault_path)
        sm = SyncManager(store, vault)
        sm.configure(tmpdir, "pass123", "merge")
        assert sm.config.enabled
        sm.disable()
        assert sm.config.enabled is False
