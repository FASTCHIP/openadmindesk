# Installation Guide

This guide provides instructions for installing OpenAdminDesk on Linux systems using AppImage, Debian/Ubuntu (.deb), and Fedora/RHEL/Rocky/Alma (.rpm) package formats.

## System Requirements

- **Operating System**: Linux desktop (Ubuntu 22.04+, Debian 12+, Fedora 38+, RHEL 9+, Rocky/Alma 9+)
- **AppImage Requirement**: `libfuse2` must be installed for AppImages to run.
- **SSH Client**: OpenSSH client is recommended (usually pre-installed on most Linux distributions).
- **Self-Contained**: No additional Python or Qt installation is required; all dependencies are bundled.

## AppImage Installation

The AppImage is a standalone executable that does not require a formal installation process.

1. **Download**: Download the `OpenAdminDesk-x86_64.AppImage` file.
2. **Make Executable**: Open a terminal in the download directory and run:
   ```bash
   chmod +x OpenAdminDesk-x86_64.AppImage
   ```
3. **Run**: Execute the AppImage:
   ```bash
   ./OpenAdminDesk-x86_64.AppImage
   ```
4. **Optional (Add to PATH)**: You can move the file to `~/.local/bin/` to run it from anywhere:
   ```bash
   mv OpenAdminDesk-x86_64.AppImage ~/.local/bin/
   ```
5. **Verify**: Check the version to ensure it runs correctly:
   ```bash
   ./OpenAdminDesk-x86_64.AppImage --version
   ```

## Debian/Ubuntu Installation (.deb)

1. **Install Package**: Use `dpkg` to install the downloaded `.deb` package:
   ```bash
   sudo dpkg -i openadmindesk_0.1.0_all.deb
   ```
2. **Fix Dependencies**: If there are any missing dependency errors, run:
   ```bash
    sudo apt install -f
   ```
3. **Run**: Launch OpenAdminDesk from your application menu or via terminal:
   ```bash
   openadmindesk
   ```
4. **Verify**:
   ```bash
   openadmindesk --version
   ```

## RPM Installation (Fedora/RHEL/Rocky/Alma) (.rpm)

1. **Install Package**: Use `rpm` or `dnf` to install the downloaded `.rpm` package:
   ```bash
   sudo rpm -ivh openadmindesk-0.1.0-1.noarch.rpm
   # OR
   sudo dnf install openadmindesk-0.1.0-1.noarch.rpm
   ```
2. **Run**: Launch OpenAdminDesk from your application menu or via terminal:
   ```bash
   openadmindesk
   ```
3. **Verify**:
   ```bash
   openadmindesk --version
   ```

## Uninstallation

- **AppImage**: Simply delete the `.AppImage` file.
- **Debian/Ubuntu**:
  ```bash
  sudo dpkg -r openadmindesk
  ```
- **RPM**:
  ```bash
  sudo rpm -e openadmindesk
  ```

## Troubleshooting

- **AppImage "fuse: failed to exec" or "cannot open shared object"**: This indicates `libfuse2` is missing. Install it using your package manager (e.g., `sudo apt install libfuse2`).
- **Package Manager Dependency Errors**: If `dpkg` or `rpm` reports missing dependencies, use the system package manager's fix command (`apt install -f` for Debian/Ubuntu) to resolve them.

## Data Locations

For power users, OpenAdminDesk stores its data in the following locations:

- **Profiles**: `~/.local/share/openadmindesk/profiles.db`
- **Vault**: `~/.local/share/openadmindesk/vault.json`
- **Settings**: `~/.local/share/openadmindesk/settings.json`
