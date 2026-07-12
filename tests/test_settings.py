"""Tests for AppSettings and SettingsStore — persistence and migration."""

from __future__ import annotations

import json
import os

from openadmindesk.core.settings import AppSettings, SettingsStore


def test_app_settings_defaults() -> None:
    """AppSettings has sensible defaults for all fields."""
    s = AppSettings()
    assert s.version == 1
    assert s.language == "en"
    assert s.window_width == 1200
    assert s.window_height == 800
    assert s.terminal_font_family == "monospace"
    assert s.terminal_font_size == 10
    assert s.terminal_bg_opacity == 255
    assert s.terminal_cursor_blink_ms == 530
    assert s.terminal_scrollback_lines == 5000
    assert s.terminal_paste_warning is True
    assert s.sftp_show_hidden_files is False
    assert s.sftp_double_click_action == "edit"
    assert s.sftp_default_path == "/"
    assert s.log_level == "INFO"


def test_settings_store_round_trip(tmp_path) -> None:
    """Save and load preserves all fields."""
    path = str(tmp_path / "settings.json")
    store = SettingsStore(path)

    original = AppSettings()
    original.language = "ru"
    original.terminal_paste_warning = False
    original.sftp_show_hidden_files = True
    original.sftp_double_click_action = "download"
    original.terminal_font_size = 14

    assert store.save(original) is True

    loaded = store.load()
    assert loaded.language == "ru"
    assert loaded.terminal_paste_warning is False
    assert loaded.sftp_show_hidden_files is True
    assert loaded.sftp_double_click_action == "download"
    assert loaded.terminal_font_size == 14
    assert loaded.version == 1


def test_settings_store_missing_file(tmp_path) -> None:
    """Loading from non-existent path returns defaults."""
    path = str(tmp_path / "nonexistent" / "settings.json")
    store = SettingsStore(path)
    s = store.load()
    assert isinstance(s, AppSettings)
    assert s.version == 1


def test_settings_store_corrupt_file(tmp_path) -> None:
    """Corrupt JSON file gracefully returns defaults."""
    path = str(tmp_path / "settings.json")
    with open(path, "w") as f:
        f.write("not valid json")

    store = SettingsStore(path)
    s = store.load()
    assert isinstance(s, AppSettings)


def test_settings_store_unknown_keys_ignored(tmp_path) -> None:
    """Unknown fields in the JSON file are silently ignored."""
    path = str(tmp_path / "settings.json")
    data = {
        "version": 1,
        "language": "de",
        "unknown_field": "should be ignored",
        "another_unknown": 42,
    }
    with open(path, "w") as f:
        json.dump(data, f)

    store = SettingsStore(path)
    s = store.load()
    assert s.language == "de"
    assert not hasattr(s, "unknown_field")


def test_settings_migration_from_v0(tmp_path) -> None:
    """Settings without a version field (v0) migrate to v1 cleanly."""
    path = str(tmp_path / "settings.json")
    data = {
        "language": "fr",
        "terminal_font_size": 12,
        "sftp_show_hidden_files": True,
    }
    with open(path, "w") as f:
        json.dump(data, f)

    store = SettingsStore(path)
    s = store.load()
    assert s.version == 1
    assert s.language == "fr"
    assert s.terminal_font_size == 12
    assert s.sftp_show_hidden_files is True
    # Missing fields get defaults
    assert s.terminal_paste_warning is True
    assert s.window_width == 1200


def test_settings_store_creates_directory(tmp_path) -> None:
    """Save creates intermediate directories."""
    nested = str(tmp_path / "a" / "b" / "settings.json")
    store = SettingsStore(nested)
    s = AppSettings()
    assert store.save(s) is True
    assert os.path.exists(nested)

def test_settings_dialog_uses_font_combo_box(tmp_path, qapp) -> None:
    from PySide6.QtWidgets import QComboBox

    from openadmindesk.ui.settings_dialog import SettingsDialog

    store = SettingsStore(str(tmp_path / "settings.json"))
    dialog = SettingsDialog(store, AppSettings())

    assert isinstance(dialog._term_font, QComboBox)
    assert not dialog._term_font.isEditable()
    assert dialog._term_font.count() >= 3
    assert dialog._term_font.findText("DejaVu Sans Mono") >= 0
