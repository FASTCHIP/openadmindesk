# RPM Package (.rpm)

To build an .rpm package for OpenAdminDesk, follow these steps:

## Prerequisites

1. Install build dependencies:
```bash
sudo dnf install rpm-build python3-devel python3-pip
sudo dnf install PyQt6 python3-paramiko python3-cryptography python3-argon2
```

## Building the .rpm package

1. Create the source structure:
```bash
mkdir -p ~/rpmbuild/{SOURCES,SPECS}
```

2. Create the spec file:
```bash
cat > ~/rpmbuild/SPECS/openadmindesk.spec << 'EOF'
Name: openadmindesk
Version: 0.1.0
Release: 1
Summary: Modern open source Linux remote administration workbench

License: GPL-3.0-or-later
URL: https://github.com/your-repo/openadmindesk
Source0: %{name}-%{version}.tar.gz

BuildRequires: python3-pyqt6, python3-paramiko, python3-cryptography, python3-argon2
BuildArch: noarch

%description
OpenAdminDesk is a modern open source remote administration workbench for Linux
desktops. It provides connection tree, tabbed terminals, SSH and SFTP workflows,
credential management, port forwarding, and remote graphical application forwarding.

%prep
%setup -n %{name}-%{version}

%build
python3 setup.py build

%install
python3 setup.py install --root=%{buildroot} --prefix=/usr

%files
%doc
%{_bindir}/openadmindesk
%{_datadir}/openadmindesk/
%{_datadir}/applications/openadmindesk.desktop
%{_datadir}/icons/hicolor/256x256/apps/openadmindesk.png

%changelog
* Thu Jul 09 2026 OpenAdminDesk Contributors <info@openadmindesk.org> 0.1.0-1
- Initial package
EOF
```

3. Create the source archive:
```bash
tar -czf ~/rpmbuild/SOURCES/openadmindesk-0.1.0.tar.gz \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    src/ pyproject.toml run.py docs/ tests/
```

4. Build the package:
```bash
rpmbuild -bb ~/rpmbuild/SPECS/openadmindesk.spec
```

The resulting .rpm package will be in `~/rpmbuild/RPMS/noarch/`.