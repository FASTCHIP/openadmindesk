"""Localization engine — load translations from JSON, provide _() function."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_current_lang = "en"
_strings: dict[str, str] = {}
_available_langs: dict[str, str] = {}  # code → native name


def _locale_dir() -> Path:
    """Find the locale directory relative to the package."""
    return Path(__file__).resolve().parent.parent / "locale"


def load_language(code: str) -> bool:
    """Load translations for a language code (e.g. 'ru', 'en').

    Returns True on success, False if the file was not found.
    """
    global _current_lang, _strings

    path = _locale_dir() / f"{code}.json"
    if not path.exists():
        logger.warning(f"Translation file not found: {path}")
        return False

    try:
        _strings = json.loads(path.read_text(encoding="utf-8"))
        _current_lang = code
        logger.info(f"Loaded language: {code} ({len(_strings)} strings)")
        return True
    except Exception as e:
        logger.error(f"Failed to load {code}: {e}")
        return False


def _(text: str) -> str:
    """Translate a string. Falls back to the original text if no translation found."""
    return _strings.get(text, text)


def current_language() -> str:
    return _current_lang


def available_languages() -> dict[str, str]:
    """Return {code: native_name} for all available .json locale files."""
    global _available_langs
    if _available_langs:
        return _available_langs

    lang_dir = _locale_dir()
    if not lang_dir.exists():
        return {"en": "English"}

    for path in sorted(lang_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            native = data.get("__language_name__", path.stem)
            _available_langs[path.stem] = native
        except Exception:
            _available_langs[path.stem] = path.stem

    if "en" not in _available_langs:
        _available_langs["en"] = "English"
    return _available_langs


# Auto-load on import
load_language("en")
