"""Versioned application settings model with JSON file storage.

This module provides a single source of truth for global behaviour
that previously lived as hardcoded constants scattered across widgets.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# Current schema version — bump when adding/removing fields with migrations
_SETTINGS_VERSION = 1

# Default path for the settings file
_SETTINGS_FILENAME = "settings.json"


def default_settings_path() -> str:
    """Return the default path for the settings JSON file."""
    from openadmindesk.platform.platform_utils import default_db_path
    db_dir = os.path.dirname(default_db_path())
    return os.path.join(db_dir, _SETTINGS_FILENAME)


@dataclass
class AppSettings:
    """Application-wide settings with defaults and versioning.

    All fields have sensible defaults so a missing or corrupt file
    can be regenerated without crashing.
    """

    version: int = _SETTINGS_VERSION

    # ── General ──────────────────────────────────────────────────────────────
    language: str = "en"
    window_width: int = 1200
    window_height: int = 800

    # ── Terminal ─────────────────────────────────────────────────────────────
    terminal_font_family: str = "monospace"
    terminal_font_size: int = 10
    terminal_font_size_min: int = 6
    terminal_font_size_max: int = 32
    terminal_bg_opacity: int = 255
    terminal_opacity_min: int = 30
    terminal_opacity_max: int = 255
    terminal_cursor_blink_ms: int = 530
    terminal_scrollback_lines: int = 5000
    terminal_default_columns: int = 80
    terminal_default_rows: int = 24
    terminal_paste_warning: bool = True

    # ── SFTP ─────────────────────────────────────────────────────────────────
    sftp_show_hidden_files: bool = False
    sftp_tree_font_size: int = 12
    sftp_double_click_action: str = "edit"  # edit | download | open
    sftp_default_path: str = "/"

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"


class SettingsStore:
    """Loads and saves AppSettings to a JSON file.

    Usage:
        store = SettingsStore("/path/to/settings.json")
        settings = store.load()
        settings.terminal_paste_warning = False
        store.save(settings)
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or default_settings_path()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> AppSettings:
        """Load settings from the JSON file, migrating if necessary."""
        if not os.path.exists(self._path):
            logger.info("Settings file not found, using defaults")
            return AppSettings()

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load settings: %s, using defaults", exc)
            return AppSettings()

        return self._from_dict(data)

    def save(self, settings: AppSettings) -> bool:
        """Save settings to the JSON file. Returns True on success."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            data = asdict(settings)
            data["version"] = _SETTINGS_VERSION
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)
            return False

    # ── migration helpers ────────────────────────────────────────────────────

    def _from_dict(self, data: dict) -> AppSettings:
        """Convert a dict (from JSON) to AppSettings, handling migration.

        Unknown keys are silently dropped; missing keys get defaults.
        """
        version = data.get("version", 0)
        migrated = self._migrate(data, version)

        # Build settings from migrated data, ignoring unknown keys
        valid_keys = set(AppSettings.__dataclass_fields__.keys())
        filtered = {k: v for k, v in migrated.items() if k in valid_keys}
        return AppSettings(**filtered)

    def _migrate(self, data: dict, from_version: int) -> dict:
        """Run version-to-version migrations."""
        current = dict(data)

        if from_version < 1:
            # Migrate from version 0 (unversioned) to version 1
            # No specific field renames needed for initial version
            current["version"] = 1

        current["version"] = _SETTINGS_VERSION
        return current
