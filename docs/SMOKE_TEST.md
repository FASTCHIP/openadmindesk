# Smoke Test

To perform a smoke test of the packaged application:

## For AppImage

1. Make the AppImage executable:
```bash
chmod +x OpenAdminDesk-x86_64.AppImage
```

2. Run the application:
```bash
./OpenAdminDesk-x86_64.AppImage
```

3. Verify that:
   - The main window opens
   - The application is responsive
   - All UI components are visible
   - No critical errors appear in the console

## For .deb Package

1. Install the package:
```bash
sudo dpkg -i openadmindesk_0.1.0-1_all.deb
```

2. Run the application:
```bash
openadmindesk
```

3. Verify that:
   - The main window opens
   - The application is responsive
   - All UI components are visible
   - No critical errors appear in the console

## For .rpm Package

1. Install the package:
```bash
sudo rpm -ivh openadmindesk-0.1.0-1.noarch.rpm
```

2. Run the application:
```bash
openadmindesk
```

3. Verify that:
   - The main window opens
   - The application is responsive
   - All UI components are visible
   - No critical errors appear in the console

## Additional Tests

1. Test basic functionality:
   - Create a profile
   - Connect to a server (if available)
   - Open a terminal tab
   - Use the profile list

2. Test advanced features:
   - Create a tunnel profile
   - Start/stop a tunnel
   - Use snippet functionality
   - Access credential vault

3. Verify dependencies:
   - SSH client is available
   - X11 forwarding works (if X11 is available)
   - Required Python modules are present
## Manual Product Workflow Smoke Checklist

Run this after major UI/session changes:

- Create SSH, RDP, Telnet, VNC, and Local Shell profiles from Session Wizard.
- Save a profile into a non-root folder and verify the connection tree shows it there.
- Open an SSH profile, resize the terminal, reconnect, and close the tab.
- Open SFTP for the same profile and browse at least one directory.
- Export profiles and verify no password/private-key passphrase/RDP gateway password is present.
- Import exported profiles and verify credentials are not hydrated as plaintext.
- Create and unlock a vault, add an account, lock/unlock, and wait for auto-lock timeout in a manual debug build.
- Open RDP/VNC/tunnel flows with a failing target and verify diagnostics are visible through captured stderr/status.


## Verified Package Smoke Commands

The following non-destructive package smoke checks were verified on the build server:

```bash
dist/OpenAdminDesk-x86_64.AppImage --version

rm -rf /tmp/oad-deb-smoke /tmp/oad-rpm-smoke /tmp/oad-appimage-smoke
mkdir -p /tmp/oad-deb-smoke /tmp/oad-rpm-smoke /tmp/oad-appimage-smoke
dpkg-deb -x dist/openadmindesk_0.1.0_all.deb /tmp/oad-deb-smoke
PYTHONPATH=/tmp/oad-deb-smoke/usr/lib/python3.12/dist-packages \
  /tmp/oad-deb-smoke/usr/bin/openadmindesk --version
test -f /tmp/oad-deb-smoke/usr/share/applications/openadmindesk.desktop
test -f /tmp/oad-deb-smoke/usr/share/icons/hicolor/scalable/apps/openadmindesk.svg

cd /tmp/oad-rpm-smoke
rpm2cpio /ai/openadmindesk/dist/openadmindesk-0.1.0-1.noarch.rpm | cpio -idmv
PYTHONPATH=/tmp/oad-rpm-smoke/usr/lib/python3.12/dist-packages \
  /tmp/oad-rpm-smoke/usr/bin/openadmindesk --version
test -f /tmp/oad-rpm-smoke/usr/share/applications/openadmindesk.desktop
test -f /tmp/oad-rpm-smoke/usr/share/icons/hicolor/scalable/apps/openadmindesk.svg

cd /tmp/oad-appimage-smoke
/ai/openadmindesk/dist/OpenAdminDesk-x86_64.AppImage --appimage-extract >/tmp/oad-appimage-smoke/extract.log
test -f squashfs-root/openadmindesk.desktop
test -f squashfs-root/openadmindesk.png
test -f squashfs-root/usr/share/applications/openadmindesk.desktop
test -f squashfs-root/usr/share/icons/hicolor/scalable/apps/openadmindesk.svg
test -f squashfs-root/usr/share/icons/hicolor/256x256/apps/openadmindesk.png
```

All three launch checks printed `OpenAdminDesk 0.1.0`; package metadata checks found the expected desktop and icon assets.
