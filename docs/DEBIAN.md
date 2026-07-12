# Debian Package (.deb)

To build a .deb package for OpenAdminDesk, follow these steps:

## Prerequisites

1. Install build dependencies:
```bash
sudo apt install dpkg-dev debhelper python3-all
```

2. Install Python dependencies:
```bash
sudo apt install python3-pyqt6 python3-paramiko python3-cryptography python3-argon2
```

## Building the .deb package

1. Create the source structure:
```bash
mkdir -p openadmindesk-0.1.0/debian
```

2. Copy source files:
```bash
cp -r src/ openadmindesk-0.1.0/
cp pyproject.toml openadmindesk-0.1.0/
cp run.py openadmindesk-0.1.0/
cp -r docs/ openadmindesk-0.1.0/
cp -r tests/ openadmindesk-0.1.0/
```

3. Create debian/control:
```bash
cat > openadmindesk-0.1.0/debian/control << 'EOF'
Source: openadmindesk
Section: utils
Priority: optional
Maintainer: OpenAdminDesk Contributors
Build-Depends: debhelper-compat (= 13), dh-python, python3-all, python3-pyqt6, python3-paramiko, python3-cryptography, python3-argon2
Standards-Version: 4.6.0

Package: openadmindesk
Architecture: all
Depends: ${python3:Depends}, ${misc:Depends}, python3-pyqt6, openssh-client
Description: Modern open source Linux remote administration workbench
 OpenAdminDesk is a modern open source remote administration workbench for Linux
 desktops. It provides connection tree, tabbed terminals, SSH and SFTP
 workflows, credential management, port forwarding, and remote
 graphical application forwarding.
EOF
```

4. Create debian/rules:
```bash
cat > openadmindesk-0.1.0/debian/rules << 'EOF'
#!/usr/bin/make -f

%:
	dh $@ --with python3

override_dh_auto_install:
	dh_auto_install
	# Install desktop file
	install -d debian/openadmindesk/usr/share/applications
	install -m 644 openadmindesk.desktop debian/openadmindesk/usr/share/applications/
	# Install icons
	install -d debian/openadmindesk/usr/share/icons/hicolor/256x256/apps
	install -m 644 openadmindesk.png debian/openadmindesk/usr/share/icons/hicolor/256x256/apps/
EOF
chmod +x openadmindesk-0.1.0/debian/rules
```

5. Create debian/copyright:
```bash
cat > openadmindesk-0.1.0/debian/copyright << 'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: OpenAdminDesk
Source: https://github.com/your-repo/openadmindesk

Files: *
Copyright: 2024 OpenAdminDesk Contributors
License: GPL-3.0-or-later

License: GPL-3.0-or-later
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 .
 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
EOF
```

6. Create debian/compat:
```bash
echo "13" > openadmindesk-0.1.0/debian/compat
```

7. Build the package:
```bash
cd openadmindesk-0.1.0
dpkg-buildpackage -us -uc -b
```

The resulting .deb package will be in the parent directory.