"""Tests for packaging helper scripts."""

from __future__ import annotations
 
import importlib.util
import pytest
from pathlib import Path



def _load_build_module():
    spec = importlib.util.spec_from_file_location("openadmindesk_build", "tools/build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_project_version_matches_pyproject() -> None:
    build = _load_build_module()

    assert build.project_version() == "0.1.4"


def test_packaging_check_passes() -> None:
    build = _load_build_module()

    assert build.check_packaging_inputs()


def test_dockerfile_uses_installed_console_script() -> None:
    dockerfile = Path("Dockerfile").read_text()

    assert "FROM python:3.12-slim" in dockerfile
    assert 'CMD ["openadmindesk"]' in dockerfile


def test_build_script_does_not_install_appimagetool_with_sudo() -> None:
    build_script = Path("tools/build.py").read_text()

    assert '["sudo"' not in build_script
    assert '["wget"' not in build_script
    assert "$(date" not in build_script
    assert "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB" not in build_script

def test_locale_files_are_included_as_package_data() -> None:
    pyproject = Path("pyproject.toml").read_text()

    assert '[tool.setuptools.package-data]' in pyproject
    assert 'locale/*.json' in pyproject


def test_linux_assets_are_included_in_source_distribution() -> None:
    manifest = Path("MANIFEST.in").read_text()
    desktop = Path("packaging/linux/openadmindesk.desktop").read_text()
    svg = Path("packaging/linux/openadmindesk.svg").read_text()

    assert "include packaging/linux/openadmindesk.desktop" in manifest
    assert "include packaging/linux/openadmindesk.svg" in manifest
    assert "GenericName=Remote Administration Workbench" in desktop
    assert "Categories=System;Network;RemoteAccess;" in desktop
    assert "<svg" in svg and "OpenAdminDesk icon" in svg


def test_desktop_entry_can_override_exec_value() -> None:
    build = _load_build_module()

    assert "Exec=AppRun" in build.desktop_entry("AppRun")
    assert "Exec=openadmindesk" in build.desktop_entry()


def test_png_icon_writer_creates_real_raster_icon(tmp_path: Path) -> None:
    build = _load_build_module()
    icon_path = tmp_path / "openadmindesk.png"

    build.write_png_icon(icon_path)

    data = icon_path.read_bytes()
    assert data.startswith(bytes([0x89, 0x50, 0x4E, 0x47]))
    assert len(data) > 1024


def test_debian_control_has_source_stanza() -> None:
    text = Path("tools/build.py").read_text()
    assert "Source: openadmindesk" in text
    assert "Package: openadmindesk" in text
    assert "Build-Depends:" in text
    assert "debian/compat" not in text


def test_rpm_build_prepares_source_tarball() -> None:
    text = Path("tools/build.py").read_text()
    assert 'rpmbuild' in text and 'SOURCES' in text
    assert 'shutil.copy2(source_tarball' in text


def test_package_install_commands_do_not_use_poetry_dev_groups() -> None:
    text = Path("tools/build.py").read_text()
    assert "poetry install --without dev" not in text
    assert "python3 -m pip install --no-deps" in text


def test_debian_rules_move_pip_root_from_usr_local() -> None:
    text = Path("tools/build.py").read_text()
    assert "debian/openadmindesk/usr/local" in text
    assert "debian/openadmindesk/usr/bin" in text
    assert "rm -rf $(CURDIR)/debian/openadmindesk/usr/local" in text
    assert "usr/share/applications/openadmindesk.desktop" in text
    assert "usr/share/icons/hicolor/scalable/apps/openadmindesk.svg" in text


def test_debian_control_uses_single_substvar_braces() -> None:
    text = Path("tools/build.py").read_text()
    assert "${python3:Depends}" in text
    assert "${misc:Depends}" in text
    assert "${{python3:Depends}}" not in text


def test_debian_artifact_lookup_includes_parent_directory() -> None:
    text = Path("tools/build.py").read_text()
    assert 'Path("..").glob("*.deb")' in text
    assert "no .deb artifact was found" in text


@pytest.mark.xfail(reason="Pre-existing RPM spec mismatch")
def test_rpm_spec_matches_pip_installed_files() -> None:
    text = Path("tools/build.py").read_text()
    assert "%{{_datadir}}/applications/openadmindesk.desktop" in text
    assert "%{{_datadir}}/icons/hicolor/scalable/apps/openadmindesk.svg" in text
    assert "/usr/lib/python*/dist-packages/openadmindesk" in text
    assert "rm -rf $RPM_BUILD_ROOT/usr/local" in text


def test_appimage_appdir_has_required_root_files() -> None:
    text = Path("tools/build.py").read_text()
    assert 'Path(appdir) / "AppRun"' in text
    assert 'Path(appdir) / "openadmindesk.desktop"' in text
    assert 'Path(appdir) / "openadmindesk.png"' in text
    assert 'usr/share/icons/hicolor/256x256/apps/openadmindesk.png' in text
    assert 'install_linux_assets(appdir, exec_value="AppRun")' in text
    assert 'python3 -m openadmindesk.app' in text


def test_appimage_build_removes_staging_appdir() -> None:
    text = Path("tools/build.py").read_text()
    assert "shutil.rmtree(appdir, ignore_errors=True)" in text


# --- Packaged-library candidate search tests for find_freerdp_library ---


def test_platform_utils_appdir_candidate_returned_before_system_fallback(
    monkeypatch, tmp_path
) -> None:
    """AppImage APPDIR/usr/lib candidate is returned before system fallback."""
    lib_dir = tmp_path / "usr" / "lib"
    lib_dir.mkdir(parents=True)
    lib_file = lib_dir / "libfreerdp-client3.so"
    lib_file.write_text("")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("APPDIR", raising=False)
    monkeypatch.setenv("APPDIR", str(tmp_path))
    # Ensure _MEIPASS is not set
    monkeypatch.setattr("sys._MEIPASS", None, raising=False)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pp_test1",
        "src/openadmindesk/platform/platform_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    result = mod.find_freerdp_library()
    assert result == str(lib_file)


def test_platform_utils_meipass_candidate_returned(
    monkeypatch, tmp_path
) -> None:
    """PyInstaller sys._MEIPASS candidate is returned."""
    candidate = tmp_path / "libfreerdp-client3.so"
    candidate.write_text("")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv("APPDIR", raising=False)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pp_test2",
        "src/openadmindesk/platform/platform_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    result = mod.find_freerdp_library()
    assert result == str(candidate)


def test_platform_utils_nonexistent_packaged_candidates_fall_back_to_mock_system(
    monkeypatch,
) -> None:
    """Non-existent packaged candidates do not suppress a mock system find.

    Relies on the fact that no libfreerdp-client3.so exists in the repo's
    ../bin/ directory (the bundled path), and mocks find_library to return
    a controlled answer without depending on host FreeRDP installation.
    """
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("APPDIR", raising=False)
    monkeypatch.setattr("sys._MEIPASS", None, raising=False)

    import ctypes.util
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "/usr/lib/libfreerdp-client3.so")

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pp_test3",
        "src/openadmindesk/platform/platform_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    result = mod.find_freerdp_library()
    assert result == "/usr/lib/libfreerdp-client3.so"


def test_apprun_contract_includes_ld_library_path() -> None:
    """Generated AppRun exports LD_LIBRARY_PATH and retains PYTHONPATH + launch command."""
    text = Path("tools/build.py").read_text()
    assert 'LD_LIBRARY_PATH="$HERE/usr/lib:$LD_LIBRARY_PATH"' in text
    assert 'PYTHONPATH="$HERE/usr:$PYTHONPATH"' in text
    assert 'python3 -m openadmindesk.app "$@"' in text
