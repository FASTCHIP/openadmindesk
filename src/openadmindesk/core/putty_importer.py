"""PuTTY session importer — parses .reg files exported from PuTTY."""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_store import ProfileStore

logger = logging.getLogger(__name__)


class PuttyImporter:
    """Parses PuTTY .reg export files and imports sessions."""

    def __init__(self, store: ProfileStore) -> None:
        self.store = store
        self._imported = 0

    def import_file(self, reg_path: str) -> Tuple[int, int]:
        """Import PuTTY sessions from a .reg file.

        Returns:
            Tuple of (imported_count, skipped_count).
        """
        try:
            with open(reg_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {reg_path}: {e}")
            return 0, 1

        # Find all session sections
        # Format: [HKEY_CURRENT_USER\Software\SimonTatham\PuTTY\Sessions\SessionName]
        session_re = re.compile(
            r"\[HKEY_CURRENT_USER\\Software\\SimonTatham\\PuTTY\\Sessions\\([^\]]+)\]"
        )

        sessions: dict[str, dict[str, str]] = {}
        current_session = None
        current_data = {}

        for line in content.split("\n"):
            line = line.strip()
            m = session_re.match(line)
            if m:
                if current_session and current_data:
                    sessions[current_session] = current_data
                current_session = m.group(1)
                current_data = {}
                continue

            # Key=value within a session
            kv = re.match(r'"([^"]+)"="([^"]*)"', line)
            if kv and current_session is not None:
                current_data[kv.group(1)] = kv.group(2)

        # Don't forget the last session
        if current_session and current_data:
            sessions[current_session] = current_data

        skipped = 0
        for name, data in sessions.items():
            # Decode URL-encoded session name
            name = self._decode_putty_name(name)
            profile = self._parse_session(name, data)
            if profile:
                profile.parent_folder = "Imported from PuTTY"
                self.store.save_profile(profile)
                self._imported += 1
            else:
                skipped += 1

        return self._imported, skipped

    def _decode_putty_name(self, name: str) -> str:
        """Decode PuTTY's %20-style URL encoding."""
        import urllib.parse
        try:
            return urllib.parse.unquote(name, encoding="utf-8")
        except Exception:
            return name

    def _parse_session(self, name: str, data: dict[str, str]) -> Optional[Profile]:
        host = data.get("HostName", "")
        if not host:
            return None

        port = int(data.get("PortNumber", 22))
        username = data.get("UserName", "")
        protocol = data.get("Protocol", "ssh")

        # Map PuTTY protocols
        session_type = SessionType.SSH
        if protocol == "telnet":
            session_type = SessionType.TELNET
            if port == 22:
                port = 23
        elif protocol in ("rlogin", "raw", "serial"):
            session_type = SessionType.TELNET  # closest match

        return Profile(
            name=name or host,
            host=host,
            port=port,
            username=username,
            session_type=session_type,
        )
