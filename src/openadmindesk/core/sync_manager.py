"""Cloud sync manager — encrypted sync file for Google Drive / Dropbox / etc."""

from __future__ import annotations

import json
import hashlib
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

SYNC_FILE_NAME = "openadmindesk_sync.oad"
SYNC_VERSION = 1


class ConflictMode(Enum):
    MERGE = "merge"           # Keep both, newer wins on name conflict
    REPLACE_LOCAL = "replace" # Overwrite local with cloud
    SEPARATE = "separate"     # Import cloud into separate folder, keep local


@dataclass
class SyncConfig:
    """Persistent sync configuration."""
    enabled: bool = False
    sync_folder: str = ""            # path to Google Drive / Dropbox folder
    sync_password_hash: str = ""     # SHA-256 of sync password (not the password itself)
    conflict_mode: str = ConflictMode.MERGE.value
    device_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    last_push_at: float = 0.0
    last_pull_at: float = 0.0


class SyncManager:
    """Manages encrypted sync between local app and cloud folder.

    The sync file is AES-256-GCM encrypted with a user-provided sync password.
    It lives in the user's cloud folder (Google Drive, Dropbox, OneDrive, etc.)
    and is synced by the cloud client automatically.

    The file contains: profiles, vault accounts, vault salt, and settings.
    """

    def __init__(self, profile_store, vault_manager) -> None:
        self.store = profile_store
        self.vault = vault_manager
        self.config = SyncConfig()
        self._config_path = Path(profile_store.db_path).parent / "sync_config.json"
        self._load_config()

    # ── configuration ─────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Load sync config from disk."""
        try:
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text())
                self.config = SyncConfig(**{k: v for k, v in data.items()
                                            if k in SyncConfig.__dataclass_fields__})
        except Exception:
            pass

    def _save_config(self) -> None:
        """Save sync config to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(self.config.__dict__, indent=2))

    def configure(self, folder: str, password: str, mode: str = "merge") -> None:
        """Enable and configure sync.

        Args:
            folder: Path to the cloud folder (e.g. ~/Google Drive/MySync)
            password: Sync encryption password
            mode: ConflictMode value ('merge', 'replace', 'separate')
        """
        self.config.sync_folder = folder
        self.config.sync_password_hash = hashlib.sha256(password.encode()).hexdigest()
        self.config.conflict_mode = mode
        self.config.enabled = True
        self._save_config()

    def disable(self) -> None:
        self.config.enabled = False
        self._save_config()

    @property
    def sync_file_path(self) -> Path:
        return Path(self.config.sync_folder) / SYNC_FILE_NAME

    # ── crypto ────────────────────────────────────────────────────────────────

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        return kdf.derive(password.encode())

    def _encrypt(self, data: str, password: str) -> str:
        """Encrypt data as base64(salt + iv + ciphertext)."""
        salt = secrets.token_bytes(16)
        key = self._derive_key(password, salt)
        iv = secrets.token_bytes(12)
        cipher = AESGCM(key)
        ct = cipher.encrypt(iv, data.encode(), None)
        # Pack: salt (16) + iv (12) + ciphertext
        combined = salt + iv + ct
        import base64
        return base64.b64encode(combined).decode()

    def _decrypt(self, encrypted: str, password: str) -> Optional[str]:
        """Decrypt base64(salt + iv + ciphertext)."""
        try:
            import base64
            raw = base64.b64decode(encrypted)
            salt = raw[:16]
            iv = raw[16:28]
            ct = raw[28:]
            key = self._derive_key(password, salt)
            cipher = AESGCM(key)
            return cipher.decrypt(iv, ct, None).decode()
        except Exception:
            return None

    # ── export / import ───────────────────────────────────────────────────────

    def export_sync(self, password: str) -> bool:
        """Export current local state to the sync file."""
        if not self.config.enabled or not self.config.sync_folder:
            return False

        folder = Path(self.config.sync_folder)
        if not folder.exists():
            logger.error(f"Sync folder does not exist: {folder}")
            return False

        try:
            data = {
                "version": SYNC_VERSION,
                "device_id": self.config.device_id,
                "updated_at": time.time(),
                "profiles": [],
                "vault_accounts": [],
                "vault_salt": "",
                "settings": {},
            }

            # Export profiles (without passwords for security — vault handles those)
            for p in self.store.load_all_profiles():
                pd = {k: v for k, v in p.__dict__.items()
                      if k not in ("password", "private_key_passphrase")}
                pd["session_type"] = pd["session_type"].value if hasattr(pd["session_type"], "value") else str(pd["session_type"])
                data["profiles"].append(pd)

            # Export vault accounts if vault is unlocked
            if self.vault.is_unlocked():
                for acc in self.vault.get_all_accounts():
                    ad = acc.__dict__.copy()
                    # Keep encrypted fields as-is (they need the vault master password)
                    data["vault_accounts"].append(ad)

            json_str = json.dumps(data, indent=2)
            encrypted = self._encrypt(json_str, password)

            self.sync_file_path.write_text(encrypted)
            self.config.last_push_at = time.time()
            self._save_config()
            logger.info(f"Sync exported to {self.sync_file_path}")
            return True
        except Exception as e:
            logger.error(f"Sync export failed: {e}")
            return False

    def import_sync(self, password: str) -> Optional[dict]:
        """Read and decrypt the sync file. Returns the raw data dict or None."""
        if not self.sync_file_path.exists():
            return None

        try:
            encrypted = self.sync_file_path.read_text()
            decrypted = self._decrypt(encrypted, password)
            if decrypted is None:
                logger.error("Sync decryption failed — wrong password?")
                return None
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Sync import failed: {e}")
            return None

    # ── sync actions ──────────────────────────────────────────────────────────

    def pull(self, password: str) -> Optional[str]:
        """Pull data from cloud and apply according to conflict mode.

        Returns:
            A result message string, or None if nothing changed.
        """
        if not self.config.enabled:
            return None

        cloud_data = self.import_sync(password)
        if cloud_data is None:
            return "No sync file found in cloud."

        # Check if cloud data is from a different device
        cloud_device = cloud_data.get("device_id", "unknown")
        is_same_device = cloud_device == self.config.device_id

        if is_same_device and cloud_data.get("updated_at", 0) <= self.config.last_push_at:
            return None  # No newer data to pull

        mode = ConflictMode(self.config.conflict_mode)

        if mode == ConflictMode.REPLACE_LOCAL:
            self._apply_replace(cloud_data, password)
            msg = "Local data replaced with cloud version."
        elif mode == ConflictMode.SEPARATE:
            self._apply_separate(cloud_data, password)
            msg = f"Cloud data imported into 'Synced from {cloud_device}' folder."
        else:  # MERGE
            merged = self._apply_merge(cloud_data, password)
            msg = f"Merged: {merged} profiles updated."

        self.config.last_pull_at = time.time()
        self._save_config()
        return msg

    def push(self, password: str) -> bool:
        """Push local data to cloud."""
        return self.export_sync(password)

    def auto_sync(self, password: str) -> Optional[str]:
        """Bidirectional sync: pull first, then push."""
        msg = self.pull(password)
        self.push(password)
        return msg

    # ── apply strategies ──────────────────────────────────────────────────────

    def _apply_replace(self, data: dict, password: str) -> None:
        """Replace all local data with cloud data."""
        # Delete all local profiles
        for p in self.store.load_all_profiles():
            self.store.delete_profile(p.name)
        # Import cloud profiles
        for pd in data.get("profiles", []):
            self._import_profile(pd)

    def _apply_separate(self, data: dict, password: str) -> None:
        """Import cloud data into a separate subfolder."""
        device = data.get("device_id", "cloud")
        folder_name = f"Synced from {device}"
        for pd in data.get("profiles", []):
            pd["parent_folder"] = folder_name
            self._import_profile(pd)

    def _apply_merge(self, data: dict, password: str) -> int:
        """Merge cloud profiles into local — keep both, cloud wins on name conflict."""
        count = 0
        local_names = {p.name for p in self.store.load_all_profiles()}
        for pd in data.get("profiles", []):
            name = pd.get("name", "")
            if name in local_names:
                # Rename cloud version to avoid conflict
                pd["name"] = f"{name} (cloud)"
            self._import_profile(pd)
            count += 1
        return count

    def _import_profile(self, pd: dict) -> None:
        """Import a single profile dict into the store."""
        from openadmindesk.core.profile import Profile, SessionType
        # Parse session_type
        st_raw = pd.pop("session_type", "ssh")
        try:
            st = SessionType(st_raw)
        except ValueError:
            st = SessionType.SSH
        pd.pop("password", None)
        pd.pop("private_key_passphrase", None)
        profile = Profile(session_type=st, **{k: v for k, v in pd.items()
                          if k in Profile.__dataclass_fields__})
        self.store.save_profile(profile)
