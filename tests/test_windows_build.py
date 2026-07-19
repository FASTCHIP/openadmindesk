"""Tests for Windows preview packaging helpers."""

from __future__ import annotations

import importlib.util
import struct
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("openadmindesk_build", "tools/build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ico_icon_writer_embeds_png_payload(tmp_path: Path) -> None:
    build = _load_build_module()
    path = tmp_path / "openadmindesk.ico"

    build.write_ico_icon(path)

    data = path.read_bytes()
    assert struct.unpack("<HHH", data[:6]) == (0, 1, 1)
    entry = struct.unpack("<BBBBHHII", data[6:22])
    assert entry == (0, 0, 0, 0, 1, 32, len(data) - 22, 22)
    assert data[22:30] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1024

    build.write_ico_icon(path, 32)
    assert struct.unpack("<BBBBHHII", path.read_bytes()[6:22])[:2] == (32, 32)


@pytest.mark.parametrize("size", [0, 257])
def test_ico_icon_writer_rejects_invalid_sizes(tmp_path: Path, size: int) -> None:
    build = _load_build_module()

    with pytest.raises(ValueError, match="ICO size must be between 1 and 256"):
        build.write_ico_icon(tmp_path / "bad.ico", size)


def test_windows_exe_builder_rejects_non_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _load_build_module()

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Windows build side effect called before platform guard")

    monkeypatch.setattr(build.sys, "platform", "linux")
    monkeypatch.setattr(build, "write_ico_icon", fail_if_called)
    monkeypatch.setattr(build, "run_command", fail_if_called)

    with pytest.raises(
        RuntimeError,
        match="Windows executable can only be built on Windows",
    ):
        build.build_windows_exe()


def test_windows_exe_builder_uses_structured_pyinstaller_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _load_build_module()
    commands: list[list[str]] = []

    def fake_run_command(
        cmd: list[str],
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd
        commands.append(cmd)
        artifact = Path("dist/OpenAdminDesk.exe")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"MZ-preview")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build.sys, "platform", "win32")
    monkeypatch.setattr(build, "run_command", fake_run_command)

    build.build_windows_exe()

    expected = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "OpenAdminDesk",
        "--icon",
        "build/windows/openadmindesk.ico",
        "--paths",
        "src",
        "--collect-all",
        "openadmindesk",
        "--copy-metadata",
        "openadmindesk",
        "--add-data",
        "C:\\Windows\\System32\\freerdp-client3.dll;.",
        "--add-data",
        "C:\\Program Files\\FreeRDP\\bin\\*.dll;.",
        "run.py",
    ]
    assert commands == [expected]
    assert Path("build/windows/openadmindesk.ico").stat().st_size > 1024
    assert Path("dist/OpenAdminDesk.exe").read_bytes() == b"MZ-preview"
    assert not {"sudo", "wget", "curl"}.intersection(expected)


def test_windows_exe_builder_requires_nonempty_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _load_build_module()

    def fake_run_command(
        cmd: list[str],
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build.sys, "platform", "win32")
    monkeypatch.setattr(build, "run_command", fake_run_command)

    with pytest.raises(
        RuntimeError,
        match=(
            "PyInstaller completed but dist/OpenAdminDesk.exe is missing or empty"
        ),
    ):
        build.build_windows_exe()


def test_pyinstaller_build_extra_is_pinned() -> None:
    pyproject = Path("pyproject.toml").read_text()

    assert 'build = ["PyInstaller>=6.21,<7"]' in pyproject
