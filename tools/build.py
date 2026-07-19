"""Package building tools for OpenAdminDesk."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
import zlib
from pathlib import Path

APP_ID = "openadmindesk"
LINUX_ASSET_DIR = Path("packaging/linux")
DESKTOP_SOURCE = LINUX_ASSET_DIR / f"{APP_ID}.desktop"
SVG_ICON_SOURCE = LINUX_ASSET_DIR / f"{APP_ID}.svg"


def project_version() -> str:
    """Read project version from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def debian_timestamp() -> str:
    """Return RFC 2822-ish timestamp for Debian changelog entries."""
    return dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")


def rpm_changelog_date() -> str:
    """Return RPM changelog date."""
    return dt.datetime.now().strftime("%a %b %d %Y")


def desktop_entry(exec_value: str = APP_ID) -> str:
    """Return the desktop entry with a package-specific Exec value."""
    text = DESKTOP_SOURCE.read_text()
    return text.replace(f"Exec={APP_ID}", f"Exec={exec_value}")


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png_icon(path: Path, size: int = 256) -> None:
    """Write a deterministic raster icon for AppImage root metadata."""
    pixels = bytearray([0, 0, 0, 0] * size * size)

    def put(x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < size and 0 <= y < size:
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes(color)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        for y in range(max(0, y0), min(size, y1)):
            for x in range(max(0, x0), min(size, x1)):
                put(x, y, color)

    def circle(cx: int, cy: int, radius: int, color: tuple[int, int, int, int]) -> None:
        radius2 = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius2:
                    put(x, y, color)

    def line(x0: int, y0: int, x1: int, y1: int, width: int, color: tuple[int, int, int, int]) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x = x0
        y = y0
        while True:
            rect(x - width // 2, y - width // 2, x + width // 2 + 1, y + width // 2 + 1, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    rect(0, 0, size, size, (24, 34, 45, 255))
    rect(30, 56, 226, 200, (34, 52, 69, 255))
    rect(46, 72, 210, 98, (47, 72, 88, 255))
    circle(62, 85, 6, (255, 107, 87, 255))
    circle(82, 85, 6, (255, 209, 102, 255))
    circle(102, 85, 6, (53, 208, 127, 255))
    line(70, 132, 98, 154, 13, (123, 223, 242, 255))
    line(98, 154, 70, 176, 13, (123, 223, 242, 255))
    rect(116, 169, 170, 183, (244, 247, 251, 255))
    rect(174, 130, 194, 190, (53, 208, 127, 255))
    rect(164, 138, 204, 160, (53, 208, 127, 255))
    line(174, 160, 182, 168, 7, (24, 34, 45, 255))
    line(182, 168, 198, 147, 7, (24, 34, 45, 255))

    raw_rows = bytearray()
    stride = size * 4
    for y in range(size):
        raw_rows.append(0)
        raw_rows.extend(pixels[y * stride:(y + 1) * stride])

    data = b"".join([
        bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)),
        _png_chunk(b"IDAT", zlib.compress(bytes(raw_rows), level=9)),
        _png_chunk(b"IEND", b""),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_ico_icon(path: Path, size: int = 256) -> None:
    """Write an ICO icon containing a PNG image."""
    if not 1 <= size <= 256:
        raise ValueError("ICO size must be between 1 and 256")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_png = Path(tmpdir) / "openadmindesk.png"
        write_png_icon(tmp_png, size)
        png_data = tmp_png.read_bytes()

    width = 0 if size == 256 else size
    height = 0 if size == 256 else size

    # Header: Reserved (2), Type (2), ImageCount (2)
    header = struct.pack("<HHH", 0, 1, 1)
    # Entry: Width (1), Height (1), ColorCount (1), Reserved (1), Planes (2), BitCount (2), Size (4), Offset (4)
    entry = struct.pack(
        "<BBBBHHII",
        width,
        height,
        0,
        0,
        1,
        32,
        len(png_data),
        22,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entry + png_data)


def install_linux_assets(root: Path | str, exec_value: str = APP_ID) -> None:
    """Install desktop integration assets under a package root."""
    root_path = Path(root)
    applications_dir = root_path / "usr/share/applications"
    scalable_icon_dir = root_path / "usr/share/icons/hicolor/scalable/apps"
    raster_icon_dir = root_path / "usr/share/icons/hicolor/256x256/apps"
    applications_dir.mkdir(parents=True, exist_ok=True)
    scalable_icon_dir.mkdir(parents=True, exist_ok=True)
    raster_icon_dir.mkdir(parents=True, exist_ok=True)
    (applications_dir / f"{APP_ID}.desktop").write_text(desktop_entry(exec_value))
    shutil.copy2(SVG_ICON_SOURCE, scalable_icon_dir / f"{APP_ID}.svg")
    write_png_icon(raster_icon_dir / f"{APP_ID}.png")


def check_packaging_inputs() -> bool:
    """Validate package metadata and build-script assumptions without building."""
    version = project_version()
    required = [
        "pyproject.toml",
        "Dockerfile",
        "src/openadmindesk/app.py",
        "MANIFEST.in",
        str(DESKTOP_SOURCE),
        str(SVG_ICON_SOURCE),
        "run.py",
    ]
    missing = [path for path in required if not Path(path).exists()]
    if missing:
        print(f"Missing required packaging inputs: {', '.join(missing)}")
        return False
    print(f"Packaging inputs OK for OpenAdminDesk {version}")
    return True


def run_command(cmd: list, cwd: str = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise


def build_python_packages():
    """Build Python packages (wheel and source)."""
    print("Building Python packages...")
    run_command([sys.executable, "-m", "poetry", "build"])


def build_appimage():
    """Build AppImage package."""
    print("Building AppImage...")

    try:
        run_command(["which", "appimagetool"])
    except subprocess.CalledProcessError:
        raise RuntimeError("appimagetool not found; install it before building AppImage")

    appdir = "AppDir"
    if os.path.exists(appdir):
        shutil.rmtree(appdir)

    os.makedirs(f"{appdir}/usr/bin")
    os.makedirs(f"{appdir}/usr/lib")
    os.makedirs(f"{appdir}/usr/share")
    os.makedirs(f"{appdir}/usr/share/metainfo")

    dist_dir = Path("dist")
    wheel_files = list(dist_dir.glob("*.whl"))
    if wheel_files:
        wheel_file = wheel_files[0]
        run_command([sys.executable, "-m", "pip", "install", "--target", f"{appdir}/usr", str(wheel_file)])

    # Bundle FreeRDP shared library
    freerdp_lib = shutil.which("libfreerdp-client3.so") or None
    if not freerdp_lib:
        for libdir in ["/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib"]:
            candidate = Path(libdir) / "libfreerdp-client3.so"
            if candidate.exists():
                freerdp_lib = str(candidate)
                break
    if freerdp_lib:
        shutil.copy2(freerdp_lib, f"{appdir}/usr/lib/")
        print(f"Bundled FreeRDP library: {freerdp_lib}")
    else:
        print("WARNING: libfreerdp-client3.so not found; RDP sessions will require system library")

    apprun_content = """#!/bin/sh
HERE=$(dirname "$(readlink -f "$0")")
export PYTHONPATH="$HERE/usr:$PYTHONPATH"
exec python3 -m openadmindesk.app "$@"
"""
    apprun_path = Path(appdir) / "AppRun"
    apprun_path.write_text(apprun_content)
    apprun_path.chmod(0o755)

    install_linux_assets(appdir, exec_value="AppRun")
    shutil.copy2(Path(appdir) / "usr/share/applications/openadmindesk.desktop", Path(appdir) / "openadmindesk.desktop")
    shutil.copy2(Path(appdir) / "usr/share/icons/hicolor/256x256/apps/openadmindesk.png", Path(appdir) / "openadmindesk.png")

    appimage_name = "OpenAdminDesk-x86_64.AppImage"
    run_command(["appimagetool", appdir, appimage_name])

    os.makedirs("dist", exist_ok=True)
    shutil.move(appimage_name, f"dist/{appimage_name}")
    shutil.rmtree(appdir, ignore_errors=True)

    print(f"AppImage created: dist/{appimage_name}")


def build_windows_exe() -> None:
    """Build the unsigned Windows preview executable with PyInstaller."""
    if sys.platform != "win32":
        raise RuntimeError("Windows executable can only be built on Windows")

    print("Building Windows executable...")
    icon_path = Path("build/windows/openadmindesk.ico")
    write_ico_icon(icon_path)
    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "OpenAdminDesk",
        "--icon", str(icon_path),
        "--paths", "src",
        "--collect-all", "openadmindesk",
        "--copy-metadata", "openadmindesk",
    ]

    # Conditionally add FreeRDP DLLs — skip if not present on build machine
    freerdp_dll = Path(r"C:\Windows\System32\freerdp-client3.dll")
    if freerdp_dll.exists():
        pyinstaller_args.extend([
            "--add-data",
            r"C:\Windows\System32\freerdp-client3.dll;.",
        ])

    freerdp_bin = Path(r"C:\Program Files\FreeRDP\bin")
    if freerdp_bin.exists() and any(freerdp_bin.glob("*.dll")):
        pyinstaller_args.extend([
            "--add-data",
            r"C:\Program Files\FreeRDP\bin\*.dll;.",
        ])

    pyinstaller_args.append("run.py")
    run_command(pyinstaller_args)

    artifact = Path("dist/OpenAdminDesk.exe")
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise RuntimeError(
            "PyInstaller completed but dist/OpenAdminDesk.exe is missing or empty"
        )
    print("Windows executable created: dist/OpenAdminDesk.exe")


def build_deb_package():
    """Build Debian package."""
    print("Building Debian package...")

    version = project_version()
    debian_dir = "debian"
    if os.path.exists(debian_dir):
        shutil.rmtree(debian_dir)

    os.makedirs(debian_dir)

    control_content = """Source: openadmindesk
Section: utils
Priority: optional
Maintainer: OpenAdminDesk Contributors <17078374+FASTCHIP@users.noreply.github.com>
Build-Depends: debhelper-compat (= 13), dh-python, python3-all, python3-setuptools, python3-wheel
Standards-Version: 4.6.2
Rules-Requires-Root: no

Package: openadmindesk
Architecture: all
Depends: ${python3:Depends}, python3-pyside6, python3-cryptography, python3-argon2-cffi, python3-paramiko, libfreerdp-client3, ${misc:Depends}
Description: Modern open source Linux remote administration workbench
 OpenAdminDesk is a modern Linux desktop application that makes SSH, SFTP,
 tunnels, credential management, and remote graphical application forwarding
 convenient from one scalable GUI.
"""
    with open(f"{debian_dir}/control", "w") as f:
        f.write(control_content)

    rules_content = """#!/usr/bin/make -f
%:
	dh $@

override_dh_auto_build:
	poetry build

override_dh_auto_install:
	python3 -m pip install --no-deps --prefix=/usr --root=$(CURDIR)/debian/openadmindesk .
	mkdir -p $(CURDIR)/debian/openadmindesk/usr/bin $(CURDIR)/debian/openadmindesk/usr/lib
	if [ -d $(CURDIR)/debian/openadmindesk/usr/local/bin ]; then mv $(CURDIR)/debian/openadmindesk/usr/local/bin/* $(CURDIR)/debian/openadmindesk/usr/bin/; fi
	if [ -d $(CURDIR)/debian/openadmindesk/usr/local/lib ]; then mv $(CURDIR)/debian/openadmindesk/usr/local/lib/* $(CURDIR)/debian/openadmindesk/usr/lib/; fi
	rm -rf $(CURDIR)/debian/openadmindesk/usr/local
	install -D -m 0644 packaging/linux/openadmindesk.desktop $(CURDIR)/debian/openadmindesk/usr/share/applications/openadmindesk.desktop
	install -D -m 0644 packaging/linux/openadmindesk.svg $(CURDIR)/debian/openadmindesk/usr/share/icons/hicolor/scalable/apps/openadmindesk.svg
"""
    with open(f"{debian_dir}/rules", "w") as f:
        f.write(rules_content)
    run_command(["chmod", "+x", f"{debian_dir}/rules"])

    changelog_content = f"""openadmindesk ({version}) unstable; urgency=medium

  * Initial release

 -- OpenAdminDesk Contributors <17078374+FASTCHIP@users.noreply.github.com>  {debian_timestamp()}
"""
    with open(f"{debian_dir}/changelog", "w") as f:
        f.write(changelog_content)

    run_command(["dpkg-buildpackage", "-us", "-uc", "-b"])

    os.makedirs("dist", exist_ok=True)
    deb_files = sorted(Path(".").glob("*.deb")) + sorted(Path("..").glob("*.deb"))
    if not deb_files:
        raise RuntimeError("dpkg-buildpackage completed but no .deb artifact was found")
    for deb_file in deb_files:
        shutil.move(str(deb_file), f"dist/{deb_file.name}")

    print(f"Debian package created: dist/{deb_files[0].name}")


def _python_sitelib() -> str:
    """Return Python site-packages/dist-packages path relative to /usr."""
    import sysconfig
    from pathlib import PurePath
    purelib = PurePath(sysconfig.get_path("purelib"))
    try:
        return str(purelib.relative_to("/usr"))
    except ValueError:
        return str(purelib.relative_to(purelib.anchor)) if purelib.is_absolute() else str(purelib)


def build_rpm_package():
    """Build RPM package."""
    print("Building RPM package...")

    try:
        run_command(["which", "rpmbuild"])
    except subprocess.CalledProcessError:
        print("rpmbuild not found. Please install rpm-build package.")
        return

    version = project_version()
    python_lib = _python_sitelib()
    source_dir = Path.home() / "rpmbuild" / "SOURCES"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_tarball = Path("dist") / f"openadmindesk-{version}.tar.gz"
    if not source_tarball.exists():
        build_python_packages()
    shutil.copy2(source_tarball, source_dir / source_tarball.name)

    spec_content = f"""Name: openadmindesk
Version: {version}
Release: 1%{{?dist}}
Summary: Modern open source Linux remote administration workbench
License: GPL-3.0-or-later
URL: https://github.com/FASTCHIP/openadmindesk
Source0: %{{name}}-%{{version}}.tar.gz
BuildArch: noarch

Requires: python3-pyside6, python3-cryptography, python3-argon2-cffi, python3-paramiko, libfreerdp-client3

%description
OpenAdminDesk is a modern Linux desktop application that makes SSH, SFTP,
tunnels, credential management, and remote graphical application forwarding
convenient from one scalable GUI.

%prep
%setup -q

%build
poetry build

%install
rm -rf $RPM_BUILD_ROOT
python3 -m pip install --no-deps --prefix=/usr --root $RPM_BUILD_ROOT .
mkdir -p $RPM_BUILD_ROOT/usr/bin $RPM_BUILD_ROOT/usr/lib
if [ -d $RPM_BUILD_ROOT/usr/local/bin ]; then mv $RPM_BUILD_ROOT/usr/local/bin/* $RPM_BUILD_ROOT/usr/bin/; fi
if [ -d $RPM_BUILD_ROOT/usr/local/lib ]; then mv $RPM_BUILD_ROOT/usr/local/lib/* $RPM_BUILD_ROOT/usr/lib/; fi
rm -rf $RPM_BUILD_ROOT/usr/local
install -D -m 0644 packaging/linux/openadmindesk.desktop $RPM_BUILD_ROOT%{{_datadir}}/applications/openadmindesk.desktop
install -D -m 0644 packaging/linux/openadmindesk.svg $RPM_BUILD_ROOT%{{_datadir}}/icons/hicolor/scalable/apps/openadmindesk.svg
find $RPM_BUILD_ROOT -type f -o -type l | sed "s|^$RPM_BUILD_ROOT||" > %{{_tmppath}}/files.list

%files -f %{{_tmppath}}/files.list

%changelog
* {rpm_changelog_date()} OpenAdminDesk Contributors <17078374+FASTCHIP@users.noreply.github.com> - {version}-1
- Initial release
"""

    with open("openadmindesk.spec", "w") as f:
        f.write(spec_content)

    run_command(["rpmbuild", "-bb", "openadmindesk.spec"])

    os.makedirs("dist", exist_ok=True)
    rpm_files = list((Path.home() / "rpmbuild/RPMS/noarch").glob("*.rpm"))
    if rpm_files:
        rpm_file = rpm_files[0]
        shutil.move(str(rpm_file), f"dist/{rpm_file.name}")
        print(f"RPM package created: dist/{rpm_file.name}")


def main():
    """Main entry point for build tools."""
    if len(sys.argv) < 2:
        print("Usage: python build.py <command>")
        print("Available commands:")
        print("  python-pkg    - Build Python packages (wheel and source)")
        print("  appimage      - Build AppImage package")
        print("  deb           - Build Debian package")
        print("  rpm           - Build RPM package")
        print("  check         - Validate packaging inputs without building")
        print("  windows-exe   - Build Windows preview executable")
        print("  all           - Build all packages")
        return

    command = sys.argv[1]

    if command == "check":
        raise SystemExit(0 if check_packaging_inputs() else 1)
    elif command == "python-pkg":
        build_python_packages()
    elif command == "appimage":
        build_appimage()
    elif command == "deb":
        build_deb_package()
    elif command == "rpm":
        build_rpm_package()
    elif command == "windows-exe":
        build_windows_exe()
    elif command == "all":
        build_python_packages()
        build_appimage()
        build_deb_package()
        build_rpm_package()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
