"""MobaXterm configuration importer — parses MobaXterm.ini and imports sessions.

This is an independent implementation for importing user configurations.
It is not affiliated with, endorsed by, or approved by Mobatek or MobaXterm.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_store import ProfileStore, Folder

logger = logging.getLogger(__name__)


def _read_ini(path: str) -> dict[str, dict[str, str]]:
    """Read a MobaXterm-style .ini file (percent signs in values).

    Returns:
        Dict of {section_name: {key: value}}.
    """
    result: dict[str, dict[str, str]] = {}
    current_section: Optional[str] = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n\r")
            # Skip empty lines and comments
            if not line or line.startswith(";"):
                continue
            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                if current_section not in result:
                    result[current_section] = {}
                continue
            # Key=value
            if "=" in line and current_section is not None:
                key, _, value = line.partition("=")
                result[current_section][key.strip()] = value

    return result

# MobaXterm protocol IDs → SessionType
_PROTO_MAP: dict[int, SessionType] = {
    109: SessionType.SSH,   # SSH
    91: SessionType.RDP,    # RDP
    95: SessionType.RDP,    # VNC → map to RDP (no VNC yet)
    130: SessionType.SSH,   # FTP → map to SSH (no FTP yet)
    140: SessionType.SSH,   # SFTP → SSH
}

# Protocol IDs we skip (WSL, local terminal, etc.)
_SKIP_PROTOCOLS = {105, 151, 196}  # WSL, Salad, etc.


class MobaXtermImporter:
    """Parses a MobaXterm.ini file and imports sessions into ProfileStore."""

    def __init__(self, store: ProfileStore) -> None:
        self.store = store
        self._imported = 0
        self._skipped = 0

    # ── public API ────────────────────────────────────────────────────────────

    def import_file(self, ini_path: str) -> Tuple[int, int]:
        """Import all sessions from a MobaXterm.ini file.

        Returns:
            Tuple of (imported_count, skipped_count).
        """
        data = _read_ini(ini_path)

        # Collect all bookmark sections
        bookmark_sections = [
            s for s in data
            if s == "Bookmarks" or re.match(r"^Bookmarks_\d+$", s)
        ]

        # Sort by suffix number to preserve order
        def _sort_key(name: str) -> int:
            m = re.search(r"(\d+)$", name)
            return int(m.group(1)) if m else 0
        bookmark_sections.sort(key=_sort_key)

        root_name = "Imported from MobaXterm"

        for section in bookmark_sections:
            section_data = data[section]
            subrep = section_data.get("subrep", section_data.get("SubRep", ""))
            if not subrep:
                self._import_section_data(section_data, parent_folder=root_name)
            else:
                # Normalize path separators
                folder_path = f"{root_name}/{subrep.replace(chr(92), '/')}"
                # Collapse double slashes
                while "//" in folder_path:
                    folder_path = folder_path.replace("//", "/")
                self._import_section_data(section_data, parent_folder=folder_path)

        return self._imported, self._skipped

    # ── internals ─────────────────────────────────────────────────────────────

    def _import_section_data(self, data: dict[str, str], parent_folder: str) -> None:
        """Import all sessions from a single section's data dict."""
        for key, raw in data.items():
            if key.lower() in ("subrep", "imgnum"):
                continue

            profile = self._parse_session(key, raw)
            if profile is None:
                self._skipped += 1
                continue

            # Ensure parent folder exists
            self._ensure_folder_path(parent_folder)

            profile.parent_folder = parent_folder
            profile.name = self._unique_name(profile.name)
            self.store.save_profile(profile)
            self._imported += 1

    def _parse_session(self, display_name: str, raw: str) -> Optional[Profile]:
        """Parse a single MobaXterm session line into a Profile."""
        # Format: #proto_id#session_id%host%port%[cred]%...params...%#Font#...
        m = re.match(r"^#(\d+)#\d+%(.+)$", raw)
        if not m:
            return None

        proto_id = int(m.group(1))
        rest = m.group(2)

        if proto_id in _SKIP_PROTOCOLS:
            return None

        session_type = _PROTO_MAP.get(proto_id, SessionType.SSH)

        # Split at the font section (everything after last `#` with font info)
        parts = rest.split("#", 1)
        params = parts[0]  # percent-encoded session params

        fields = params.split("%")

        if len(fields) < 2:
            return None

        host = fields[0] if fields[0] else ""
        port_str = fields[1] if len(fields) > 1 else "22"
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 22 if session_type == SessionType.SSH else 3389

        # Username (field 2) — may be wrapped in [brackets] for credential ref
        username = ""
        if len(fields) > 2 and fields[2]:
            username = fields[2].strip("[]")
            # Unescape backslashes
            username = username.replace("\\\\", "\\")

        # Clean display name: remove trailing ([credential]) or (credential) suffix
        clean_name = display_name.strip()
        clean_name = re.sub(r"\s*\(\[.*?\]\)\s*$", "", clean_name)
        clean_name = re.sub(r"\s*\(.*?\)\s*$", "", clean_name)
        if not clean_name:
            clean_name = host or display_name

        return Profile(
            name=clean_name,
            host=host,
            port=port,
            username=username,
            session_type=session_type,
        )

    def _ensure_folder_path(self, path: str) -> None:
        """Create all folders along a path like 'Root/Child/Grandchild'."""
        parts = path.split("/")
        for i in range(len(parts)):
            subpath = "/".join(parts[:i + 1])
            # Simple check — save_folder uses INSERT OR REPLACE
            self.store.save_folder(Folder(name=subpath, parent=None))

    def _unique_name(self, name: str) -> str:
        """Ensure the profile name is unique by appending a suffix if needed."""
        existing = self.store.load_profile(name)
        if existing is None:
            return name
        i = 1
        while self.store.load_profile(f"{name} ({i})") is not None:
            i += 1
        return f"{name} ({i})"
