"""SQLite profile store with caching and async support."""

from __future__ import annotations

import sqlite3
import time
import asyncio
import logging
from typing import Optional, List, Dict
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from openadmindesk.core.profile import Profile, SessionType


class Folder:
    """A named folder for grouping profiles."""
    def __init__(self, name: str, parent: Optional[str] = None):
        self.name = name
        self.parent = parent  # parent folder name or None for root

    def __repr__(self) -> str:
        return f"Folder({self.name!r})"


class ProfileStore:
    """SQLite-based profile storage with caching and async support."""

    def __init__(self, db_path: str = "profiles.db", cache_ttl: int = 300) -> None:
        """Initialize the profile store.

        Args:
            db_path: Path to SQLite database file
            cache_ttl: Time-to-live for cache entries in seconds (default: 5 minutes)
        """
        self.db_path = db_path
        self.cache_ttl = cache_ttl
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="db_async")
        self._init_database()

        # Cache for loaded profiles
        self._profile_cache: Dict[str, Dict] = {}
        self._cache_lock = Lock()

        # Cache for all profiles list
        self._all_profiles_cache: Optional[List[Profile]] = None
        self._all_profiles_cache_time: float = 0

        # Module logger
        self.logger = logging.getLogger(__name__)

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection (thread-safe)."""
        uri = self.db_path.startswith("file:")
        conn = sqlite3.connect(self.db_path, check_same_thread=False, uri=uri)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database_sync(self) -> None:
        """Initialize the database synchronously."""
        # For in-memory databases, we need to ensure the connection persists
        # or use a shared named memory database
        actual_path = self.db_path
        if self.db_path == ':memory:':
            actual_path = 'file::memory:?cache=shared'
            self.db_path = actual_path

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    username TEXT,
                    session_type TEXT DEFAULT 'ssh',
                    parent_folder TEXT,
                    credential_id TEXT,
                    password TEXT,
                    private_key_path TEXT,
                    private_key_passphrase TEXT,
                    use_ssh_agent BOOLEAN DEFAULT 0,
                    compression BOOLEAN DEFAULT 0,
                    keep_alive BOOLEAN DEFAULT 1,
                    ssh_config TEXT,
                    proxy_command TEXT,
                    rdp_drive_redirection BOOLEAN DEFAULT 0,
                    rdp_drive_path TEXT,
                    rdp_printer_redirection BOOLEAN DEFAULT 0,
                    rdp_multimon BOOLEAN DEFAULT 0,
                    rdp_gateway TEXT,
                    rdp_gateway_username TEXT,
                    rdp_gateway_password TEXT,
                    rdp_gateway_credential_id TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(name)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    parent TEXT,
                    UNIQUE(name)
                )
            """)
            # Migrations: add missing columns for older databases
            self._migrate_add_column(conn, "profiles", "session_type", "TEXT DEFAULT 'ssh'")
            self._migrate_add_column(conn, "profiles", "parent_folder", "TEXT")
            self._migrate_add_column(conn, "profiles", "credential_id", "TEXT")
            self._migrate_add_column(conn, "profiles", "private_key_passphrase", "TEXT")
            self._migrate_add_column(conn, "profiles", "rdp_drive_redirection", "BOOLEAN DEFAULT 0")
            self._migrate_add_column(conn, "profiles", "rdp_drive_path", "TEXT")
            self._migrate_add_column(conn, "profiles", "rdp_printer_redirection", "BOOLEAN DEFAULT 0")
            self._migrate_add_column(conn, "profiles", "rdp_multimon", "BOOLEAN DEFAULT 0")
            self._migrate_add_column(conn, "profiles", "rdp_gateway", "TEXT")
            self._migrate_add_column(conn, "profiles", "rdp_gateway_username", "TEXT")
            self._migrate_add_column(conn, "profiles", "rdp_gateway_password", "TEXT")
            self._migrate_add_column(conn, "profiles", "rdp_gateway_credential_id", "TEXT")
            self._migrate_add_column(conn, "profiles", "notes", "TEXT")
            # Step 8 metadata columns
            self._migrate_add_column(conn, "profiles", "favorite", "BOOLEAN DEFAULT 0")
            self._migrate_add_column(conn, "profiles", "tags", "TEXT DEFAULT ''")
            self._migrate_add_column(conn, "profiles", "icon_id", "TEXT")
            self._migrate_add_column(conn, "profiles", "last_connected", "TEXT")
            self._migrate_add_column(conn, "profiles", "last_error", "TEXT")
            self._migrate_add_column(conn, "profiles", "last_duration", "REAL")

    def _init_database(self) -> None:
        """Initialize the database."""
        self._init_database_sync()

    def _migrate_add_column(self, conn, table: str, column: str, col_type: str) -> None:
        """Add a column if it doesn't exist (safe migration)."""
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except Exception:
            pass  # Column already exists

    async def _run_db(self, func, *args, **kwargs):
        """Run a database operation in the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: func(*args, **kwargs))

    def _validate_profile_before_save(self, profile: Profile) -> bool:
        """Validate profile credentials before saving to database.

        Returns:
            bool: True if validation passes (even with warnings), False if critical validation fails
        """
        # Check if we have password/passphrase without credential_id
        if (profile.password is not None and profile.password != "" and
            (profile.credential_id is None or profile.credential_id == "")):
            self.logger.warning(
                "Profile '%s' has password but no credential_id. "
                "Password will be stored in database without credential reference.",
                profile.name
            )

        if (profile.private_key_passphrase is not None and profile.private_key_passphrase != "" and
            (profile.credential_id is None or profile.credential_id == "")):
            self.logger.warning(
                "Profile '%s' has private_key_passphrase but no credential_id. "
                "Passphrase will be stored in database without credential reference.",
                profile.name
            )

        # Check if we have gateway password without credential_id
        if (profile.rdp_gateway_password is not None and profile.rdp_gateway_password != "" and
            (profile.rdp_gateway_credential_id is None or profile.rdp_gateway_credential_id == "")):
            self.logger.warning(
                "Profile '%s' has RDP gateway password but no rdp_gateway_credential_id. "
                "Gateway password will be stored in database without credential reference.",
                profile.name
            )

        # Validation passes (rejection is False as required)
        return True

    def _save_profile_sync(self, profile: Profile) -> bool:
        """Save a profile to the database synchronously."""
        try:
            # Validate before saving
            if not self._validate_profile_before_save(profile):
                return False

            # For credential-backed saves, we want to persist SQL NULL for passwords/passphrases
            # without mutating the caller's profile object
            # If credential_id is set, store NULL in DB for all passwords; otherwise, store the actual values
            password_to_save = None if profile.credential_id else profile.password
            private_key_passphrase_to_save = None if profile.credential_id else profile.private_key_passphrase
            rdp_gateway_password_to_save = None if profile.credential_id else profile.rdp_gateway_password

            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO profiles
                    (name, host, port, username, session_type, parent_folder, credential_id,
                      password, private_key_path, private_key_passphrase,
                      use_ssh_agent, compression, keep_alive, ssh_config, proxy_command,
                     rdp_drive_redirection, rdp_drive_path,
                     rdp_printer_redirection, rdp_multimon,
                     rdp_gateway, rdp_gateway_username, rdp_gateway_password,
                     rdp_gateway_credential_id, notes,
                     created_at, updated_at,
                     favorite, tags, icon_id, last_connected, last_error, last_duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?)
                """, (
                    profile.name, profile.host, profile.port, profile.username,
                    profile.session_type.value, profile.parent_folder,
                    profile.credential_id,
                    password_to_save, profile.private_key_path,
                    private_key_passphrase_to_save,
                    int(profile.use_ssh_agent),
                    int(profile.compression), int(profile.keep_alive), profile.ssh_config,
                    profile.proxy_command,
                    int(profile.rdp_drive_redirection), profile.rdp_drive_path,
                    int(profile.rdp_printer_redirection), int(profile.rdp_multimon),
                    profile.rdp_gateway, profile.rdp_gateway_username,
                    rdp_gateway_password_to_save, profile.rdp_gateway_credential_id,
                    profile.notes,
                    profile.created_at, profile.updated_at,
                    int(profile.favorite), profile.tags, profile.icon_id,
                    profile.last_connected, profile.last_error, profile.last_duration
                ))

            # Update cache - evict the profile from cache so immediate load reflects DB values
            self._remove_from_cache(profile.name)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save profile: {e}")
            return False

    def save_profile(self, profile: Profile) -> bool:
        """Save a profile to the database."""
        return self._save_profile_sync(profile)

    async def save_profile_async(self, profile: Profile) -> bool:
        """Save a profile to the database asynchronously."""
        return await self._run_db(self._save_profile_sync, profile)

    def _load_profile_sync(self, name: str) -> Optional[Profile]:
        """Load a profile from the database synchronously."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM profiles WHERE name = ?",
                    (name,)
                )
                row = cursor.fetchone()

                if row:
                    profile = self._row_to_profile(row)
                    # Cache the profile
                    self._add_to_cache(profile)
                    return profile
                return None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load profile: {e}")
            return None

    def load_profile(self, name: str) -> Optional[Profile]:
        """Load a profile from the database with caching (sync)."""
        # Check cache first
        cached_profile = self._get_from_cache(name)
        if cached_profile:
            return cached_profile

        return self._load_profile_sync(name)

    async def load_profile_async(self, name: str) -> Optional[Profile]:
        """Load a profile from the database asynchronously."""
        # Check cache first
        cached_profile = self._get_from_cache(name)
        if cached_profile:
            return cached_profile

        return await self._run_db(self._load_profile_sync, name)

    def _load_all_profiles_sync(self) -> List[Profile]:
        """Load all profiles from the database synchronously."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM profiles")
                rows = cursor.fetchall()

                profiles = []
                for row in rows:
                    profile = self._row_to_profile(row)
                    profiles.append(profile)
                    # Cache individual profiles too
                    self._add_to_cache(profile)

                return profiles
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load all profiles: {e}")
            return []

    def load_all_profiles(self) -> List[Profile]:
        """Load all profiles from the database with caching (sync)."""
        current_time = time.time()

        # Check if cache is still valid
        if (self._all_profiles_cache is not None and
            current_time - self._all_profiles_cache_time < self.cache_ttl):
            return self._all_profiles_cache.copy()

        profiles = self._load_all_profiles_sync()

        # Update all profiles cache
        with self._cache_lock:
            self._all_profiles_cache = profiles.copy()
            self._all_profiles_cache_time = current_time

        return profiles

    async def load_all_profiles_async(self) -> List[Profile]:
        """Load all profiles from the database asynchronously."""
        current_time = time.time()

        # Check if cache is still valid
        if (self._all_profiles_cache is not None and
            current_time - self._all_profiles_cache_time < self.cache_ttl):
            return self._all_profiles_cache.copy()

        profiles = await self._run_db(self._load_all_profiles_sync)

        # Update all profiles cache
        with self._cache_lock:
            self._all_profiles_cache = profiles.copy()
            self._all_profiles_cache_time = current_time

        return profiles

    def _delete_profile_sync(self, name: str) -> bool:
        """Delete a profile from the database synchronously."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM profiles WHERE name = ?",
                    (name,)
                )
                deleted = cursor.rowcount > 0

                if deleted:
                    # Remove from cache
                    self._remove_from_cache(name)
                    # Invalidate all profiles cache
                    self._all_profiles_cache = None

                return deleted
        except Exception:
            return False

    def delete_profile(self, name: str) -> bool:
        """Delete a profile from the database."""
        return self._delete_profile_sync(name)

    async def delete_profile_async(self, name: str) -> bool:
        """Delete a profile from the database asynchronously."""
        return await self._run_db(self._delete_profile_sync, name)

    def _row_to_profile(self, row) -> Profile:
        """Convert a database row to a Profile object."""
        is_row_object = hasattr(row, 'keys')

        name = row['name'] if is_row_object else row[1]
        host = row['host'] if is_row_object else row[2]
        port = row['port'] if is_row_object else row[3]
        username = row['username'] if is_row_object else row[4]

        # Parse session_type
        st_raw = row['session_type'] if is_row_object else row[5]
        try:
            session_type = SessionType(st_raw) if st_raw else SessionType.SSH
        except ValueError:
            session_type = SessionType.SSH

        parent_folder = row['parent_folder'] if is_row_object else row[6]
        credential_id = row['credential_id'] if is_row_object else row[7]

        password = row['password'] if is_row_object else row[8]
        private_key_path = row['private_key_path'] if is_row_object else row[9]
        private_key_passphrase = row['private_key_passphrase'] if is_row_object else row[10]
        use_ssh_agent = bool(row['use_ssh_agent'] if is_row_object else row[11])
        compression = bool(row['compression'] if is_row_object else row[12])
        keep_alive = bool(row['keep_alive'] if is_row_object else row[13])
        ssh_config = row['ssh_config'] if is_row_object else row[14]
        proxy_command = row['proxy_command'] if is_row_object else row[15]
        rdp_drive_redirection = bool(row['rdp_drive_redirection'] if is_row_object else row[16])
        rdp_drive_path = row['rdp_drive_path'] if is_row_object else row[17]
        rdp_printer_redirection = bool(row['rdp_printer_redirection'] if is_row_object else row[18])
        rdp_multimon = bool(row['rdp_multimon'] if is_row_object else row[19])
        rdp_gateway = row['rdp_gateway'] if is_row_object else row[20]
        rdp_gateway_username = row['rdp_gateway_username'] if is_row_object else row[21]
        rdp_gateway_password = row['rdp_gateway_password'] if is_row_object else row[22]
        rdp_gateway_credential_id = (
            row['rdp_gateway_credential_id']
            if is_row_object and 'rdp_gateway_credential_id' in row.keys()
            else None
        )
        notes = row['notes'] if is_row_object else row[24]
        created_at = row['created_at'] if is_row_object else row[25]
        updated_at = row['updated_at'] if is_row_object else row[26]
        favorite = bool(row['favorite'] if is_row_object else row[27])
        tags = row['tags'] if is_row_object else row[28]
        icon_id = (
            row['icon_id']
            if is_row_object and 'icon_id' in row.keys()
            else (row[29] if not is_row_object and len(row) > 29 else None)
        )
        last_connected = row['last_connected'] if is_row_object else row[30]
        last_error = row['last_error'] if is_row_object else row[31]
        last_duration = row['last_duration'] if is_row_object else row[32]

        return Profile(
            name=name, host=host, port=port, username=username,
            session_type=session_type,
            parent_folder=parent_folder, credential_id=credential_id,
            password=password, private_key_path=private_key_path,
            private_key_passphrase=private_key_passphrase,
            use_ssh_agent=use_ssh_agent, compression=compression,
            keep_alive=keep_alive, ssh_config=ssh_config,
            proxy_command=proxy_command,
            rdp_drive_redirection=rdp_drive_redirection,
            rdp_drive_path=rdp_drive_path,
            rdp_printer_redirection=rdp_printer_redirection,
            rdp_multimon=rdp_multimon,
            rdp_gateway=rdp_gateway,
            rdp_gateway_username=rdp_gateway_username,
            rdp_gateway_password=rdp_gateway_password,
            rdp_gateway_credential_id=rdp_gateway_credential_id,
            notes=notes,
            created_at=created_at,
            updated_at=updated_at,
            favorite=favorite, tags=tags,
            icon_id=icon_id,
            last_connected=last_connected,
            last_error=last_error,
            last_duration=last_duration,
        )

    def _add_to_cache(self, profile: Profile) -> None:
        """Add a profile to the cache."""
        with self._cache_lock:
            self._profile_cache[profile.name] = {
                'profile': profile,
                'timestamp': time.time()
            }

    def _get_from_cache(self, name: str) -> Optional[Profile]:
        """Get a profile from cache if it's still valid."""
        with self._cache_lock:
            cached = self._profile_cache.get(name)
            if cached:
                # Check if cache entry is expired
                if time.time() - cached['timestamp'] < self.cache_ttl:
                    return cached['profile']
                else:
                    # Remove expired entry
                    del self._profile_cache[name]
            return None

    def _remove_from_cache(self, name: str) -> None:
        """Remove a profile from cache."""
        with self._cache_lock:
            self._profile_cache.pop(name, None)

    def _update_cache(self, profile: Profile) -> None:
        """Update cache with a profile (add or update existing)."""
        with self._cache_lock:
            self._profile_cache[profile.name] = {
                'profile': profile,
                'timestamp': time.time()
            }
            # Invalidate all profiles cache
            self._all_profiles_cache = None

    def clear_cache(self) -> None:
        """Clear all cached profiles."""
        with self._cache_lock:
            self._profile_cache.clear()
            self._all_profiles_cache = None
            self._all_profiles_cache_time = 0

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                'cached_profiles': len(self._profile_cache),
                'all_profiles_cached': self._all_profiles_cache is not None
            }

    def close(self) -> None:
        """Shutdown the thread pool executor."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    # ── Folder operations ─────────────────────────────────────────────────

    def _save_folder_sync(self, folder: Folder) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO folders (name, parent) VALUES (?, ?)",
                    (folder.name, folder.parent)
                )
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save folder: {e}")
            return False

    def save_folder(self, folder: Folder) -> bool:
        return self._save_folder_sync(folder)

    def _delete_folder_sync(self, name: str) -> bool:
        try:
            with self._get_connection() as conn:
                # Unlink profiles in this folder
                conn.execute(
                    "UPDATE profiles SET parent_folder = NULL WHERE parent_folder = ?",
                    (name,)
                )
                # Delete sub-folders
                conn.execute(
                    "DELETE FROM folders WHERE parent = ?", (name,)
                )
                # Delete the folder itself
                conn.execute("DELETE FROM folders WHERE name = ?", (name,))
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to delete folder: {e}")
            return False

    def delete_folder(self, name: str) -> bool:
        return self._delete_folder_sync(name)

    def _load_all_folders_sync(self) -> list[Folder]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT name, parent FROM folders").fetchall()
                return [Folder(name=r[0], parent=r[1]) for r in rows]
        except Exception:
            return []

    def load_all_folders(self) -> list[Folder]:
        return self._load_all_folders_sync()

    def move_profile_to_folder(self, profile_name: str, folder_name: Optional[str]) -> bool:
        """Move a profile into a folder (or root if folder_name is None)."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE profiles SET parent_folder = ? WHERE name = ?",
                    (folder_name, profile_name)
                )
            self._remove_from_cache(profile_name)
            self._all_profiles_cache = None
            return True
        except Exception:
            return False
