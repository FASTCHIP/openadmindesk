"""Platform utilities — OS detection, data directories, and safe subprocess helpers."""

from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from typing import Optional


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform == "linux"


def is_macos() -> bool:
    return sys.platform == "darwin"


def _app_dir() -> Path:
    """Return the directory where the application executable/script lives.

    For PyInstaller: the directory containing the .exe.
    For regular Python: the project root (parent of src/openadmindesk).
    """
    # PyInstaller sets sys.frozen = True, and sys.executable is the .exe path
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Regular Python: go up from this file to project root
    # this file:  src/openadmindesk/platform/platform_utils.py
    # __file__:   .../src/openadmindesk/platform/platform_utils.py
    return Path(__file__).resolve().parent.parent.parent.parent


def is_portable() -> bool:
    """Check if the app is running in portable mode.

    Portable mode is detected by the presence of a `.portable` file
    in the application directory. All data (profiles, vault, sync config)
    is stored alongside the app rather than in system directories.
    """
    marker = _app_dir() / ".portable"
    return marker.exists()


def enable_portable_mode() -> Path:
    """Create the .portable marker file and return the app directory."""
    marker = _app_dir() / ".portable"
    marker.touch()
    return _app_dir()


def data_dir() -> Path:
    """Return the platform-appropriate application data directory.

    Portable mode: stores everything in the app directory.
    Otherwise: uses the platform-standard location.
    """
    if is_portable():
        path = _app_dir() / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    if is_windows():
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif is_macos():
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = Path(base) / "openadmindesk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> str:
    """Return the default path for profiles.db."""
    return str(data_dir() / "profiles.db")


def default_vault_path() -> str:
    """Return the default path for vault.json."""
    return str(data_dir() / "vault.json")


def find_rdp_binary() -> Optional[str]:
    """Locate an RDP client binary for the current platform.

    Linux: xfreerdp (bundled or system)
    Windows: mstsc.exe (built-in)
    macOS: none (user must install)
    """
    if is_windows():
        mstsc = shutil.which("mstsc.exe") or os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "mstsc.exe"
        )
        if os.path.exists(mstsc):
            return mstsc
        return None

    # Linux: check bundled first, then system
    bundled = Path(__file__).resolve().parent.parent / "bin" / "xfreerdp"
    if bundled.exists() and os.access(bundled, os.X_OK):
        return str(bundled)
    return shutil.which("xfreerdp")


def is_x11_available() -> bool:
    """Check if X11 forwarding is available on this platform."""
    if is_windows():
        return False
    if is_macos():
        return bool(os.environ.get("DISPLAY"))
    # Linux
    if os.environ.get("DISPLAY"):
        return True
    if os.path.exists("/tmp/.X11-unix/X0"):
        return True
    return False


def safe_popen_kwargs() -> dict:
    """Return platform-safe kwargs for subprocess.Popen.

    On Linux: start_new_session=True (detach from parent).
    On Windows: CREATE_NEW_PROCESS_GROUP via creationflags.
    """
    if is_windows():
        import subprocess
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def ssh_default_port() -> int:
    return 22


def rdp_default_port() -> int:
    return 3389
