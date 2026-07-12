# Dependencies

OpenAdminDesk is **self-contained** — SSH/SFTP use paramiko (Python), terminal emulation uses pyte.
All Python dependencies are declared in `pyproject.toml`.

## Linux (Ubuntu/Debian)

```bash
# System: Qt xcb plugin support
sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-xkb1 libxkbcommon-x11-0 libgl1

# Optional: RDP client
sudo apt install freerdp2-x11

# Debian/RPM/AppImage package build helpers
sudo apt install debhelper-compat dh-python python3-all python3-setuptools python3-wheel
sudo apt install libfuse2t64 rpm
# appimagetool is not in Ubuntu apt; install the AppImageKit appimagetool binary
# into PATH before running `python3 tools/build.py appimage`.

# Install the app
pip install -e ".[dev]"
```

## Windows

No system dependencies required — everything is pure Python or included:

```powershell
pip install -e ".[dev]"
python -m openadmindesk.app
```

RDP uses the built-in `mstsc.exe` — no extra installation needed.

### Creating a Windows .exe

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name OpenAdminDesk run.py
```

### Portable mode

Run once with `--portable` to create the marker:

```powershell
OpenAdminDesk.exe --portable
```

This creates a `.portable` file in the app directory. All data (profiles.db,
vault.json, sync config) will be stored in `./data/` alongside the executable.

**Copy the entire folder to any Windows computer — everything comes with it.**

To exit portable mode, delete the `.portable` file.

## macOS

```bash
pip install -e ".[dev]"
python3 -m openadmindesk.app
```

RDP requires installing a client manually (e.g. Microsoft Remote Desktop from App Store).

# RHEL-family Dependencies

To build and run OpenAdminDesk on RHEL-family distributions (Fedora, Rocky Linux, AlmaLinux), you need the following dependencies:

## Build Dependencies
```bash
sudo dnf install python3-devel python3-pip python3-setuptools python3-wheel
sudo dnf install python3-pyside6 pyside6-tools
sudo dnf install mesa-libGL-devel mesa-libGLU-devel
sudo dnf install libX11-devel libXext-devel libXfixes-devel libXi-devel libXrandr-devel libXrender-devel
sudo dnf install libxcb-xfixes0 libxcb-xinerama0 libxcb-randr0
sudo dnf install libxss-devel alsa-lib-devel
```

## Runtime Dependencies
```bash
sudo dnf install python3-pyside6
sudo dnf install openssh
sudo dnf install xorg-x11-server-Xorg
```

## Optional Dependencies
```bash
sudo dnf install python3-paramiko  # For SFTP functionality
sudo dnf install python3-cryptography  # For encryption
sudo dnf install python3-argon2-cffi  # For password hashing
```
## Supported Linux Targets For Packaging

Current packaging smoke coverage targets:

- Debian/Ubuntu family with Python 3.12+, Qt/PySide6 runtime libraries, OpenSSH client, FreeRDP/VNC viewers as optional protocol helpers.
- RPM family package generation is verified with `rpmbuild` from the Ubuntu `rpm` package.
- AppImage generation is verified with preinstalled AppImageKit `appimagetool`; build scripts do not download binaries or use sudo automatically.

Verified smoke checks in this stabilization pass:

- `python3 tools/build.py check`
- `python3 tools/build.py python-pkg`
- `python3 tools/build.py deb`
- `python3 tools/build.py rpm`
- `python3 tools/build.py appimage`
- `dist/OpenAdminDesk-x86_64.AppImage --version`
- `python3 -m pip install --no-deps . -t /tmp/openadmindesk-install-smoke`
- `PYTHONPATH=/tmp/openadmindesk-install-smoke python3 -m openadmindesk.app --version`

