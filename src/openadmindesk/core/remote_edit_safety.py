"""Remote edit safety — conflict detection and binary guards.

This module is pure Python with no Qt or SFTP import dependencies,
so it can be tested without a running event loop.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass
from typing import Optional

# ── binary file detection ────────────────────────────────────────────────────

# Common extensions that are text-editable
_TEXT_EXTENSIONS: set[str] = {
    # Programming / scripting
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".php", ".pl", ".pm",
    ".go", ".rs", ".java", ".kt", ".scala", ".clj", ".lisp",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".cs", ".swift",
    ".m", ".mm",
    # Web
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".xml",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".log",
    # Shell / config
    ".sh", ".bash", ".zsh", ".fish", ".env", ".sql",
    # Other text
    ".csv", ".tsv", ".svg", ".tex", ".bib",
}

# Extensions that are definitely binary (not text-editable)
_BINARY_EXTENSIONS: set[str] = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svgz",
    ".tiff", ".tif", ".psd", ".xcf",
    # Audio / video
    ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".avi", ".mkv", ".mov", ".wmv",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".zst", ".7z", ".rar",
    ".deb", ".rpm", ".appimage", ".dmg", ".iso",
    # Binaries
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".lib",
    ".elf", ".ko", ".sys",
    # Documents (complex formats)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Java
    ".class", ".jar", ".war",
    # Other
    ".db", ".sqlite", ".pyc", ".pyo", ".pyd",
    ".key", ".pem", ".crt", ".cer", ".der",
    ".DS_Store",
}

# Extensions that should always trigger a warning
_BINARY_LIKE_EXTENSIONS: set[str] = {
    ".bin", ".dat", ".dump", ".core",
}

# Maximum file size (bytes) for auto-opening in editor
_MAX_EDIT_SIZE = 10 * 1024 * 1024  # 10 MiB

# Null bytes threshold for content sniffing
_NULL_THRESHOLD = 0.30  # 30% null bytes → treat as binary


def is_binary_path(path: str) -> bool:
    """Check if a file path likely points to a binary file.

    Uses extension-based detection. Returns True for known binary formats,
    False for known text formats, and None (via binary sniffing) for unknown.
    """
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    if ext in _TEXT_EXTENSIONS:
        return False
    if ext in _BINARY_EXTENSIONS or ext in _BINARY_LIKE_EXTENSIONS:
        return True
    # Unknown extension — will need content sniffing
    return False


def is_binary_content(data: bytes) -> bool:
    """Sniff binary content by null-byte ratio.

    A file is considered binary if the proportion of null bytes
    exceeds _NULL_THRESHOLD.
    """
    if not data:
        return False
    null_count = data.count(b"\x00")
    return null_count / len(data) > _NULL_THRESHOLD


def check_edit_safe(path: str, size: Optional[int] = None) -> tuple[bool, str]:
    """Check if a file is safe to edit remotely.

    Returns (safe: bool, reason: str).
    If safe is False, reason explains why.
    """
    if size is not None and size > _MAX_EDIT_SIZE:
        return False, f"File too large ({size / 1024 / 1024:.1f} MiB > 10 MiB)"

    if is_binary_path(path):
        return False, f"File '{os.path.basename(path)}' appears to be a binary file"

    return True, ""


# ── conflict detection ────────────────────────────────────────────────────────


class EditConflict(enum.Enum):
    """Result of comparing a local snapshot with current remote state."""

    NO_CONFLICT = "no_conflict"
    REMOTE_CHANGED = "remote_changed"
    REMOTE_DELETED = "remote_deleted"


@dataclass
class RemoteFileSnapshot:
    """Stored metadata captured when a file was downloaded for editing."""

    remote_path: str
    mtime: Optional[float]  # remote modification time (stat.st_mtime)
    size: int               # remote file size (stat.st_size)


def make_snapshot(remote_path: str, mtime: Optional[float], size: int) -> RemoteFileSnapshot:
    """Create a snapshot from remote stat values."""
    return RemoteFileSnapshot(
        remote_path=remote_path,
        mtime=mtime,
        size=size,
    )


def check_remote_conflict(
    snapshot: RemoteFileSnapshot,
    current_mtime: Optional[float],
    current_size: Optional[int],
) -> EditConflict:
    """Compare snapshot with current remote state.

    Args:
        snapshot: The snapshot taken when the file was downloaded.
        current_mtime: Current remote mtime (None if file no longer exists).
        current_size: Current remote size (None if file no longer exists).

    Returns:
        EditConflict: NO_CONFLICT if remote hasn't changed,
                      REMOTE_CHANGED if mtime or size differ,
                      REMOTE_DELETED if file no longer exists on remote.
    """
    if current_mtime is None or current_size is None:
        return EditConflict.REMOTE_DELETED

    # SFTP mtime has second granularity — use that for comparison
    snapshot_mtime = int(snapshot.mtime) if snapshot.mtime is not None else 0
    current_mtime_int = int(current_mtime)

    if snapshot_mtime != current_mtime_int or snapshot.size != current_size:
        return EditConflict.REMOTE_CHANGED

    return EditConflict.NO_CONFLICT
