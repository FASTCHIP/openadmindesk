"""Tests for remote edit safety logic — independent of Qt and SFTP."""

from __future__ import annotations

from openadmindesk.core.remote_edit_safety import (
    EditConflict,
    check_edit_safe,
    check_remote_conflict,
    is_binary_content,
    is_binary_path,
    make_snapshot,
)


# ── is_binary_path ───────────────────────────────────────────────────────────


def test_is_binary_path_text_extensions() -> None:
    """Known text extensions return False."""
    assert is_binary_path("script.py") is False
    assert is_binary_path("index.html") is False
    assert is_binary_path("style.css") is False
    assert is_binary_path("data.json") is False
    assert is_binary_path("readme.md") is False
    assert is_binary_path("config.yaml") is False
    assert is_binary_path("main.c") is False
    assert is_binary_path("main.rs") is False
    assert is_binary_path("main.go") is False


def test_is_binary_path_binary_extensions() -> None:
    """Known binary extensions return True."""
    assert is_binary_path("image.png") is True
    assert is_binary_path("archive.zip") is True
    assert is_binary_path("binary.exe") is True
    assert is_binary_path("library.so") is True
    assert is_binary_path("document.pdf") is True
    assert is_binary_path("music.mp3") is True
    assert is_binary_path("video.mp4") is True


def test_is_binary_path_unknown_extension() -> None:
    """Unknown extensions return False (will trigger content sniffing later)."""
    assert is_binary_path("file.xyz") is False
    assert is_binary_path("file.123") is False


def test_is_binary_path_no_extension() -> None:
    """Files without extension return False."""
    assert is_binary_path("Makefile") is False
    assert is_binary_path("Dockerfile") is False
    assert is_binary_path("README") is False


def test_is_binary_path_case_insensitive() -> None:
    """Extension matching is case-insensitive."""
    assert is_binary_path("image.PNG") is True
    assert is_binary_path("Script.PY") is False
    assert is_binary_path("Archive.ZIP") is True


# ── is_binary_content ────────────────────────────────────────────────────────


def test_is_binary_content_empty() -> None:
    """Empty content is not binary."""
    assert is_binary_content(b"") is False


def test_is_binary_content_ascii_text() -> None:
    """Plain ASCII text is not binary."""
    text = b"Hello, world!\nThis is a text file.\n" * 100
    assert is_binary_content(text) is False


def test_is_binary_content_utf8_text() -> None:
    """UTF-8 encoded text (including non-ASCII) is not binary."""
    text = "Привет, мир!\n日本語\n".encode("utf-8") * 50
    assert is_binary_content(text) is False


def test_is_binary_content_with_null_bytes() -> None:
    """Content with many null bytes is binary."""
    data = b"Hello\x00\x00\x00World"  # 3 nulls out of 13 = 23% — below threshold
    assert is_binary_content(data) is False

    # Above threshold
    data2 = b"AB\x00\x00\x00\x00\x00CD"  # 5 nulls out of 9 = 55%
    assert is_binary_content(data2) is True


def test_is_binary_content_all_null() -> None:
    """All-null content is binary."""
    assert is_binary_content(b"\x00" * 100) is True


# ── check_edit_safe ──────────────────────────────────────────────────────────


def test_check_edit_safe_text_file() -> None:
    """A normal-sized text file is safe."""
    safe, reason = check_edit_safe("file.py", size=4096)
    assert safe is True
    assert reason == ""


def test_check_edit_safe_binary_file() -> None:
    """A binary file is not safe."""
    safe, reason = check_edit_safe("image.png", size=4096)
    assert safe is False
    assert "binary" in reason.lower()


def test_check_edit_safe_too_large() -> None:
    """A file >10 MiB is not safe."""
    safe, reason = check_edit_safe("large.log", size=20 * 1024 * 1024)
    assert safe is False
    assert "large" in reason.lower()


def test_check_edit_safe_no_size() -> None:
    """Without a size, only extension is checked."""
    safe, reason = check_edit_safe("script.py")
    assert safe is True


# ── make_snapshot & check_remote_conflict ────────────────────────────────────


def test_make_snapshot() -> None:
    """make_snapshot creates a RemoteFileSnapshot with correct fields."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.0, size=500)
    assert snapshot.remote_path == "/remote/file.txt"
    assert snapshot.mtime == 1000.0
    assert snapshot.size == 500


def test_conflict_no_conflict() -> None:
    """Same mtime and size means no conflict."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.0, size=500)
    result = check_remote_conflict(snapshot, current_mtime=1000.0, current_size=500)
    assert result == EditConflict.NO_CONFLICT


def test_conflict_remote_changed_mtime() -> None:
    """Different mtime means remote changed."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.0, size=500)
    result = check_remote_conflict(snapshot, current_mtime=2000.0, current_size=500)
    assert result == EditConflict.REMOTE_CHANGED


def test_conflict_remote_changed_size() -> None:
    """Different size means remote changed."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.0, size=500)
    result = check_remote_conflict(snapshot, current_mtime=1000.0, current_size=600)
    assert result == EditConflict.REMOTE_CHANGED


def test_conflict_remote_deleted() -> None:
    """None mtime/size means remote deleted."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.0, size=500)
    result = check_remote_conflict(snapshot, current_mtime=None, current_size=None)
    assert result == EditConflict.REMOTE_DELETED


def test_conflict_mtime_second_granularity() -> None:
    """Comparison uses integer mtime (SFTP second granularity)."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.1, size=500)
    # 1000 vs 1000 — same second
    result = check_remote_conflict(snapshot, current_mtime=1000.9, current_size=500)
    assert result == EditConflict.NO_CONFLICT


def test_conflict_mtime_different_second() -> None:
    """Different integer seconds triggers conflict."""
    snapshot = make_snapshot("/remote/file.txt", mtime=1000.1, size=500)
    result = check_remote_conflict(snapshot, current_mtime=1001.0, current_size=500)
    assert result == EditConflict.REMOTE_CHANGED
