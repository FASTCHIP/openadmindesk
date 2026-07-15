"""Vault management with master password."""

from __future__ import annotations

import os
import json
import tempfile
import secrets
import time
import logging
import asyncio
import hashlib
import hmac
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import argon2.low_level
import argon2.exceptions
from argon2.low_level import Type as Argon2Type

from openadmindesk.core.account import Account
from openadmindesk.core.vault_format import VaultFormat, detect_version, LATEST_VERSION

logger = logging.getLogger(__name__)

# --- Argon2id v2 constants ---
_ARGON2_TIME_COST = 2
_ARGON2_MEMORY_COST = 19456  # KiB
_ARGON2_PARALLELISM = 1
_ARGON2_HASH_LEN = 32  # bytes
_ARGON2_VERSION = argon2.low_level.ARGON2_VERSION  # 19 (0x13)

# Safe bounds for Argon2 parameters (inclusive)
_ARGON2_TIME_MIN = 1
_ARGON2_TIME_MAX = 10
_ARGON2_MEMORY_MIN = 8192
_ARGON2_MEMORY_MAX = 262144
_ARGON2_PARALLELISM_MIN = 1
_ARGON2_PARALLELISM_MAX = 8


class VaultManager:
    """Manages encrypted vault with master password."""

    def __init__(
        self,
        vault_path: str = "vault.json",
        auto_lock_timeout_seconds: Optional[int] = 900,
    ) -> None:
        """Initialize the vault manager."""
        self.vault_path = vault_path
        self.auto_lock_timeout_seconds = auto_lock_timeout_seconds
        self._master_key: Optional[bytes] = None
        self._vault_data: Optional[dict] = None
        self._is_unlocked = False
        self._last_activity_at: Optional[float] = None

        # Session cache for decrypted accounts
        self._account_cache: Dict[str, Dict] = {}  # account_id -> {account: Account, cached_at: float}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_hits = 0
        self._cache_misses = 0

        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vault_async")

    async def _run_blocking(self, func, *args, **kwargs):
        """Run a blocking operation in the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: func(*args, **kwargs))

    def _utc_now_iso(self) -> str:
        """Return current UTC time as ISO 8601 string."""
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def setup_master_password(self, master_password: str) -> bool:
        """Setup master password for the vault (v2 Argon2id).

        Snapshots prior internal state so that on any failure (Argon derivation,
        vault save, etc.) the manager state is restored to what it was before
        the call. Never leaves stale v2 partial state.
        """
        # Snapshot prior state
        prior_master_key = self._master_key
        prior_vault_data = self._vault_data
        prior_is_unlocked = self._is_unlocked
        prior_last_activity_at = self._last_activity_at

        try:
            # Generate a 16-byte salt (32 hex chars)
            salt = secrets.token_bytes(16)

            # Derive encryption key using Argon2id with default parameters
            params = {
                "time_cost": _ARGON2_TIME_COST,
                "memory_cost": _ARGON2_MEMORY_COST,
                "parallelism": _ARGON2_PARALLELISM,
                "hash_len": _ARGON2_HASH_LEN,
                "version": _ARGON2_VERSION,
            }
            key = self._derive_key_v2(master_password, salt, params)

            # Compute password verifier (HMAC-SHA256, full 64 hex chars)
            password_hash = self._compute_v2_verifier(key)

            # Store the key and create v2 vault structure
            self._master_key = key
            self._vault_data = VaultFormat.create_empty_vault(version=LATEST_VERSION)
            now = self._utc_now_iso()
            self._vault_data["salt"] = salt.hex()
            self._vault_data["kdf"] = "argon2id"
            self._vault_data["kdf_params"] = params
            self._vault_data["password_hash"] = password_hash
            self._vault_data["created_at"] = now
            self._vault_data["updated_at"] = now

            # Save the vault atomically; check return value explicitly
            if not self._save_vault():
                # Restore prior state on save failure
                self._master_key = prior_master_key
                self._vault_data = prior_vault_data
                self._is_unlocked = prior_is_unlocked
                self._last_activity_at = prior_last_activity_at
                logger.error("Failed to save vault during master password setup")
                return False

            return True
        except argon2.exceptions.Argon2Error:
            # Restore prior state on Argon derivation failure; no password in log
            self._master_key = prior_master_key
            self._vault_data = prior_vault_data
            self._is_unlocked = prior_is_unlocked
            self._last_activity_at = prior_last_activity_at
            logger.error("Argon2 derivation failed during master password setup")
            return False
        except Exception as e:
            # Restore prior state on any other failure
            self._master_key = prior_master_key
            self._vault_data = prior_vault_data
            self._is_unlocked = prior_is_unlocked
            self._last_activity_at = prior_last_activity_at
            logger.error(f"Failed to setup master password: {e}")
            return False

    def unlock(self, master_password: str) -> bool:
        """Unlock the vault with master password.

        Supports v1 (LEGACY_VERSION "1.0") vaults with PBKDF2 and
        v2 (LATEST_VERSION 2) vaults with Argon2id.
        Unknown versions return False.
        """
        try:
            # Load the vault file
            if not os.path.exists(self.vault_path):
                return False

            with open(self.vault_path, 'r') as f:
                vault_data = json.load(f)

            # Detect version
            version_num = detect_version(vault_data)

            # Support v1 (PBKDF2)
            if version_num == 1:
                return self._unlock_v1(master_password, vault_data)

            # Support v2 (Argon2id)
            if version_num == 2:
                return self._unlock_v2(master_password, vault_data)

            # Unknown version
            return False
        except Exception as e:
            logger.error(f"Failed to unlock vault: {e}")
            return False

    def _unlock_v1(self, master_password: str, vault_data: Dict) -> bool:
        """Unlock a v1 vault using PBKDF2. Called by unlock()."""
        try:
            # Validate vault structure
            if not VaultFormat.validate_vault_format(vault_data):
                return False

            # Reject empty salt or key_hash before derivation (fail closed)
            salt_str = vault_data.get("salt", "")
            key_hash_str = vault_data.get("key_hash", "")
            if not salt_str or not key_hash_str:
                return False

            # Extract kdf parameters from vault (v1 PBKDF2)
            kdf_params = vault_data.get("kdf_params", {})
            iterations = kdf_params.get("iterations", 100000)
            length = kdf_params.get("length", 32)

            # Apply safe bounds
            if not isinstance(iterations, int) or iterations < 100000 or iterations > 10_000_000:
                iterations = 100000
            if not isinstance(length, int) or length != 32:
                length = 32

            # Derive key from password using stored/default params
            salt = bytes.fromhex(vault_data["salt"])
            key = self._derive_key(master_password, salt, iterations=iterations, length=length)

            # Verify password by comparing key hash using constant-time comparison
            expected_hash = vault_data.get("key_hash", "")
            if expected_hash:
                actual_hash = hashlib.sha256(key).hexdigest()[:16]
                if not hmac.compare_digest(actual_hash, expected_hash):
                    return False  # Wrong password

            # Store key and data
            self._master_key = key
            self._vault_data = vault_data
            self._is_unlocked = True
            self._touch()
            self._clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to unlock v1 vault: {e}")
            return False

    def _unlock_v2(self, master_password: str, vault_data: Dict) -> bool:
        """Unlock a v2 vault using Argon2id. Called by unlock()."""
        try:
            # Validate vault structure
            if not VaultFormat.validate_vault_format(vault_data):
                return False

            # Reject empty salt or password_hash before derivation (fail closed)
            salt_str = vault_data.get("salt", "")
            expected_hash = vault_data.get("password_hash", "")
            if not salt_str or not expected_hash:
                return False

            # Extract and validate Argon2 parameters
            kdf_params = vault_data.get("kdf_params", {})
            time_cost = kdf_params.get("time_cost", _ARGON2_TIME_COST)
            memory_cost = kdf_params.get("memory_cost", _ARGON2_MEMORY_COST)
            parallelism = kdf_params.get("parallelism", _ARGON2_PARALLELISM)
            hash_len = kdf_params.get("hash_len", _ARGON2_HASH_LEN)
            version = kdf_params.get("version", _ARGON2_VERSION)

            # Reject bool disguised as int before safe-bounds check
            for name, val in [("time_cost", time_cost), ("memory_cost", memory_cost),
                              ("parallelism", parallelism), ("hash_len", hash_len),
                              ("version", version)]:
                if isinstance(val, bool) or not isinstance(val, int):
                    logger.error("v2 unlock rejected: %s is not an int", name)
                    return False

            # Enforce safe bounds (fail closed on out-of-range)
            if not (_ARGON2_TIME_MIN <= time_cost <= _ARGON2_TIME_MAX):
                logger.error("v2 unlock rejected: time_cost %s out of range", time_cost)
                return False
            if not (_ARGON2_MEMORY_MIN <= memory_cost <= _ARGON2_MEMORY_MAX):
                logger.error("v2 unlock rejected: memory_cost %s out of range", memory_cost)
                return False
            if not (_ARGON2_PARALLELISM_MIN <= parallelism <= _ARGON2_PARALLELISM_MAX):
                logger.error("v2 unlock rejected: parallelism %s out of range", parallelism)
                return False
            if hash_len != _ARGON2_HASH_LEN:
                logger.error("v2 unlock rejected: hash_len %s != %s", hash_len, _ARGON2_HASH_LEN)
                return False
            if version != _ARGON2_VERSION:
                logger.error("v2 unlock rejected: version %s != %s", version, _ARGON2_VERSION)
                return False

            # Derive key using Argon2id
            salt = bytes.fromhex(vault_data["salt"])
            key = self._derive_key_v2(master_password, salt, {
                "time_cost": time_cost,
                "memory_cost": memory_cost,
                "parallelism": parallelism,
                "hash_len": hash_len,
                "version": version,
            })

            # Verify password using HMAC-SHA256 verifier (constant-time)
            actual_hash = self._compute_v2_verifier(key)
            if not hmac.compare_digest(actual_hash, expected_hash):
                return False  # Wrong password

            # Store key and data
            self._master_key = key
            self._vault_data = vault_data
            self._is_unlocked = True
            self._touch()
            self._clear_cache()
            return True
        except argon2.exceptions.Argon2Error:
            # Fail closed: do not leak password details
            logger.error("Argon2 derivation failed during v2 unlock")
            return False
        except Exception as e:
            logger.error(f"Failed to unlock v2 vault: {e}")
            return False

    def lock(self) -> None:
        """Lock the vault."""
        self._master_key = None
        self._vault_data = None
        self._is_unlocked = False
        self._last_activity_at = None
        self._clear_cache()

    def _get_cached_account(self, account_id: str) -> Optional[Account]:
        """Get account from cache if valid."""
        if account_id not in self._account_cache:
            return None

        cache_entry = self._account_cache[account_id]
        cached_at = cache_entry.get('cached_at', 0)

        # Check if cache entry is expired
        if time.time() - cached_at > self._cache_ttl:
            del self._account_cache[account_id]
            return None

        self._cache_hits += 1
        return cache_entry['account']

    def _set_cached_account(self, account: Account) -> None:
        """Cache an account."""
        self._account_cache[account.id] = {
            'account': account,
            'cached_at': time.time()
        }
        self._cache_misses += 1

    def _clear_cache(self) -> None:
        """Clear all cached accounts."""
        self._account_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def _clear_expired_cache(self) -> None:
        """Clear expired cache entries."""
        current_time = time.time()
        expired_ids = []

        for account_id, cache_entry in self._account_cache.items():
            if current_time - cache_entry.get('cached_at', 0) > self._cache_ttl:
                expired_ids.append(account_id)

        for account_id in expired_ids:
            del self._account_cache[account_id]

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cached_accounts': len(self._account_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_ttl_seconds': self._cache_ttl
        }

    def _touch(self) -> None:
        """Record activity for idle auto-lock accounting."""
        if self._is_unlocked:
            self._last_activity_at = time.time()

    def _ensure_unlocked(self) -> bool:
        """Return False and lock the vault when idle timeout has elapsed."""
        if not self._is_unlocked:
            return False
        if (
            self.auto_lock_timeout_seconds is not None
            and self._last_activity_at is not None
            and time.time() - self._last_activity_at >= self.auto_lock_timeout_seconds
        ):
            self.lock()
            return False
        return True

    def is_unlocked(self) -> bool:
        """Check if vault is unlocked and enforce idle auto-lock."""
        return self._ensure_unlocked()

    def _derive_key(self, password: str, salt: bytes, iterations: int = 100000, length: int = 32) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        return key

    def _derive_key_v2(self, password: str, salt: bytes,
                       params: Optional[Dict[str, int]] = None) -> bytes:
        """Derive encryption key from password using Argon2id.

        Args:
            password: The master password.
            salt: 16-byte salt (32 hex chars).
            params: Dict with time_cost, memory_cost, parallelism, hash_len,
                    version. If None or missing keys, defaults are used.

        Returns:
            32 bytes of derived key material.

        Raises:
            ValueError: If parameters are out of safe bounds or non-int/bool.
            argon2.exceptions.Argon2Error: If Argon2 derivation itself fails.
        """
        if params is None:
            params = {}

        time_cost = params.get("time_cost", _ARGON2_TIME_COST)
        memory_cost = params.get("memory_cost", _ARGON2_MEMORY_COST)
        parallelism = params.get("parallelism", _ARGON2_PARALLELISM)
        hash_len = params.get("hash_len", _ARGON2_HASH_LEN)
        version = params.get("version", _ARGON2_VERSION)

        # Reject bool disguised as int
        for name, val in [("time_cost", time_cost), ("memory_cost", memory_cost),
                          ("parallelism", parallelism), ("hash_len", hash_len),
                          ("version", version)]:
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(
                    f"{name} must be an int, got {type(val).__name__}"
                )

        # Enforce safe bounds
        if not (_ARGON2_TIME_MIN <= time_cost <= _ARGON2_TIME_MAX):
            raise ValueError(
                f"time_cost {time_cost} out of range "
                f"[{_ARGON2_TIME_MIN}, {_ARGON2_TIME_MAX}]"
            )
        if not (_ARGON2_MEMORY_MIN <= memory_cost <= _ARGON2_MEMORY_MAX):
            raise ValueError(
                f"memory_cost {memory_cost} out of range "
                f"[{_ARGON2_MEMORY_MIN}, {_ARGON2_MEMORY_MAX}]"
            )
        if not (_ARGON2_PARALLELISM_MIN <= parallelism <= _ARGON2_PARALLELISM_MAX):
            raise ValueError(
                f"parallelism {parallelism} out of range "
                f"[{_ARGON2_PARALLELISM_MIN}, {_ARGON2_PARALLELISM_MAX}]"
            )
        if hash_len != _ARGON2_HASH_LEN:
            raise ValueError(
                f"hash_len must be {_ARGON2_HASH_LEN}, got {hash_len}"
            )
        if version != _ARGON2_VERSION:
            raise ValueError(
                f"version must be {_ARGON2_VERSION}, got {version}"
            )

        try:
            key = argon2.low_level.hash_secret_raw(
                secret=password.encode("utf-8"),
                salt=salt,
                time_cost=time_cost,
                memory_cost=memory_cost,
                parallelism=parallelism,
                hash_len=hash_len,
                type=Argon2Type.ID,
                version=_ARGON2_VERSION,
            )
            return key
        except argon2.exceptions.Argon2Error:
            # Fail closed: do not leak password or intermediate values in logs
            logger.error("Argon2 key derivation failed (v2)")
            raise

    @staticmethod
    def _compute_v2_verifier(derived_key: bytes) -> str:
        """Compute the v2 password verifier using HMAC-SHA256.

        HMAC-SHA256(derived_key, b"openadmindesk-vault-v2-verifier")
        produces 32 bytes, returned as a 64-character hex string.

        Each unlock attempt still performs the full Argon2id derivation
        before verification; the HMAC verifier is used only to check
        correctness of the derived key material.
        """
        context = b"openadmindesk-vault-v2-verifier"
        return hmac.new(derived_key, context, hashlib.sha256).hexdigest()

    def _encrypt_data(self, data: str) -> tuple[str, str]:
        """Encrypt data using AES-GCM."""
        if not self._master_key:
            raise RuntimeError("Vault not unlocked")

        # Generate a random IV
        iv = secrets.token_bytes(12)

        # Create AES-GCM cipher
        cipher = AESGCM(self._master_key)

        # Encrypt the data
        ciphertext = cipher.encrypt(iv, data.encode(), None)

        # Return IV and ciphertext as hex strings
        return iv.hex(), ciphertext.hex()

    def _decrypt_data(self, iv_hex: str, ciphertext_hex: str) -> str:
        """Decrypt data using AES-GCM."""
        if not self._master_key:
            raise RuntimeError("Vault not unlocked")

        # Convert hex to bytes
        iv = bytes.fromhex(iv_hex)
        ciphertext = bytes.fromhex(ciphertext_hex)

        # Create AES-GCM cipher
        cipher = AESGCM(self._master_key)

        # Decrypt the data
        plaintext = cipher.decrypt(iv, ciphertext, None)

        return plaintext.decode()

    def add_account(self, account: Account) -> bool:
        """Add an account to the vault."""
        if not self._is_unlocked:
            return False

        # Create a copy of the account to avoid mutating the original
        account_copy = Account(**account.__dict__)

        # Snapshot current accounts before mutation
        original_accounts = self._vault_data["accounts"][:]

        try:
            # Encrypt sensitive data in the copy only
            if account_copy.password:
                iv, ciphertext = self._encrypt_data(account_copy.password)
                account_copy.password = f"{iv}:{ciphertext}"

            if account_copy.private_key:
                iv, ciphertext = self._encrypt_data(account_copy.private_key)
                account_copy.private_key = f"{iv}:{ciphertext}"

            if account_copy.private_key_passphrase:
                iv, ciphertext = self._encrypt_data(account_copy.private_key_passphrase)
                account_copy.private_key_passphrase = f"{iv}:{ciphertext}"

            # Upsert by account.id: if ID exists replace exactly that entry; else append
            account_id = account_copy.id
            found = False
            for i, acc_data in enumerate(self._vault_data["accounts"]):
                if acc_data.get("id") == account_id:
                    self._vault_data["accounts"][i] = account_copy.__dict__
                    found = True
                    break

            # If not found, append the new account
            if not found:
                self._vault_data["accounts"].append(account_copy.__dict__)

            # Save the vault
            save_success = self._save_vault()

            if not save_success:
                # Restore snapshot on failure
                self._vault_data["accounts"] = original_accounts
                logger.warning(f"Failed to save vault for account ID {account_id}, changes reverted")
                return False

            # Clear cache only on successful save
            self._clear_cache()

            return True
        except Exception as e:
            # Restore snapshot on failure - ensure original_accounts is available
            self._vault_data["accounts"] = original_accounts
            logger.error(f"Failed to add account to vault: {e}")
            return False

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get an account from the vault."""
        if not self._is_unlocked:
            return None

        # Check cache first
        cached_account = self._get_cached_account(account_id)
        if cached_account is not None:
            return cached_account

        try:
            # Find the account
            for account_data in self._vault_data["accounts"]:
                if account_data.get("id") == account_id:
                    # Create Account object
                    account = Account(**account_data)

                    # Decrypt sensitive data
                    if account.password and ':' in account.password:
                        iv, ciphertext = account.password.split(':', 1)
                        account.password = self._decrypt_data(iv, ciphertext)

                    if account.private_key and ':' in account.private_key:
                        iv, ciphertext = account.private_key.split(':', 1)
                        account.private_key = self._decrypt_data(iv, ciphertext)

                    if account.private_key_passphrase and ':' in account.private_key_passphrase:
                        iv, ciphertext = account.private_key_passphrase.split(':', 1)
                        account.private_key_passphrase = self._decrypt_data(iv, ciphertext)

                    # Cache the decrypted account
                    self._set_cached_account(account)

                    return account

            return None
        except Exception as e:
            logger.error(f"Failed to get account from vault: {e}")
            return None

    def get_all_accounts(self) -> List[Account]:
        """Get all accounts from the vault."""
        if not self._is_unlocked:
            return []

        # Clear expired cache entries first
        self._clear_expired_cache()

        # Check if we have cached accounts
        if len(self._account_cache) == len(self._vault_data["accounts"]):
            # Return cached accounts
            return [cache_entry['account'] for cache_entry in self._account_cache.values()]

        accounts = []
        try:
            for account_data in self._vault_data["accounts"]:
                # Create Account object
                account = Account(**account_data)

                # Decrypt sensitive data
                if account.password and ':' in account.password:
                    iv, ciphertext = account.password.split(':', 1)
                    account.password = self._decrypt_data(iv, ciphertext)

                if account.private_key and ':' in account.private_key:
                    iv, ciphertext = account.private_key.split(':', 1)
                    account.private_key = self._decrypt_data(iv, ciphertext)

                if account.private_key_passphrase and ':' in account.private_key_passphrase:
                    iv, ciphertext = account.private_key_passphrase.split(':', 1)
                    account.private_key_passphrase = self._decrypt_data(iv, ciphertext)

                accounts.append(account)

                # Cache the decrypted account
                self._set_cached_account(account)
            self._touch()
        except Exception as e:
            logger.error(f"Failed to get all accounts from vault: {e}")
            return []

        return accounts

    def remove_account(self, account_id: str) -> bool:
        """Remove an account from the vault."""
        if not self._is_unlocked:
            return False

        # Snapshot current accounts before mutation
        original_accounts = self._vault_data["accounts"][:]

        try:
            # Find and remove the account
            for i, account_data in enumerate(self._vault_data["accounts"]):
                if account_data.get("id") == account_id:
                    self._vault_data["accounts"].pop(i)
                    save_success = self._save_vault()

                    if not save_success:
                        # Restore snapshot on failure
                        self._vault_data["accounts"] = original_accounts
                        logger.warning(f"Failed to save vault for account ID {account_id}, changes reverted")
                        return False

                    # Clear cache since vault data changed
                    self._clear_cache()

                    return True
            return False
        except Exception as e:
            # Restore snapshot on exception
            self._vault_data["accounts"] = original_accounts
            logger.error(f"Failed to remove account {account_id}: {e}")
            return False

    def _save_vault(self) -> bool:
        """Save the vault atomically with restrictive file permissions.

        If the vault data contains an 'updated_at' metadata field,
        it is updated to the current UTC ISO timestamp before saving.
        Old v1 vaults without metadata remain readable and unchanged.

        On save failure the prior updated_at value (or absence) is restored
        in-memory so the next save attempt sees a correct starting state.
        """
        # Snapshot prior updated_at presence/value before mutation
        had_updated_at = False
        prior_updated_at = None
        if self._vault_data and "updated_at" in self._vault_data:
            had_updated_at = True
            prior_updated_at = self._vault_data["updated_at"]

        # Update updated_at if metadata is present
        if self._vault_data and "updated_at" in self._vault_data:
            self._vault_data["updated_at"] = self._utc_now_iso()

        temp_path = None
        try:
            vault_json = VaultFormat.serialize_vault(self._vault_data)
            vault_dir = os.path.dirname(os.path.abspath(self.vault_path)) or "."
            os.makedirs(vault_dir, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                prefix=".vault-",
                suffix=".tmp",
                dir=vault_dir,
                text=True,
            )
            try:
                # Temp file already gets 0o600 via mkstemp default umask,
                # but explicitly set it so permissions are correct regardless
                os.chmod(temp_path, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(vault_json)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self.vault_path)
                # temp_path replaced successfully, clear it so finally doesn't unlink
                temp_path = None
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

            return True
        except Exception as e:
            # Restore prior updated_at in-memory on failure
            if self._vault_data is not None:
                if had_updated_at:
                    self._vault_data["updated_at"] = prior_updated_at
                else:
                    self._vault_data.pop("updated_at", None)
            logger.error(f"Failed to save vault: {e}")
            return False

    # --- Async methods ---

    async def setup_master_password_async(self, master_password: str) -> bool:
        """Setup master password for the vault asynchronously."""
        return await self._run_blocking(self.setup_master_password, master_password)

    async def unlock_async(self, master_password: str) -> bool:
        """Unlock the vault with master password asynchronously."""
        return await self._run_blocking(self.unlock, master_password)

    async def lock_async(self) -> None:
        """Lock the vault asynchronously."""
        return await self._run_blocking(self.lock)

    async def add_account_async(self, account: Account) -> bool:
        """Add an account to the vault asynchronously."""
        return await self._run_blocking(self.add_account, account)

    async def get_account_async(self, account_id: str) -> Optional[Account]:
        """Get an account from the vault asynchronously."""
        return await self._run_blocking(self.get_account, account_id)

    async def get_all_accounts_async(self) -> List[Account]:
        """Get all accounts from the vault asynchronously."""
        return await self._run_blocking(self.get_all_accounts)

    async def remove_account_async(self, account_id: str) -> bool:
        """Remove an account from the vault asynchronously."""
        return await self._run_blocking(self.remove_account, account_id)

    def close(self) -> None:
        """Shutdown the thread pool executor."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
