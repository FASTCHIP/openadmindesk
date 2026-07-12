"""X11 forwarding utilities — cross-platform."""

from __future__ import annotations

import os
from typing import Optional

from openadmindesk.platform.platform_utils import is_linux, is_macos, is_x11_available


class X11Detector:
    """Detects X11/Xwayland support."""

    @staticmethod
    def is_x11_available() -> bool:
        """Check if X11 is available on this platform."""
        return is_x11_available()

    @staticmethod
    def is_xwayland_available() -> bool:
        """Check if Xwayland is available."""
        if not is_linux():
            return False
        try:
            import subprocess
            result = subprocess.run(
                ["pgrep", "Xwayland"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_x11_display() -> Optional[str]:
        return os.environ.get("DISPLAY")

    @staticmethod
    def get_x11_auth() -> Optional[str]:
        if not is_linux() and not is_macos():
            return None
        try:
            import subprocess
            result = subprocess.run(
                ["xauth", "list"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
