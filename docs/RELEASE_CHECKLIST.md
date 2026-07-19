# Release Checklist

Use this checklist before tagging any release. Check each item manually on a clean install.

## Build

- [ ] AppImage builds without errors (`python tools/build.py appimage`)
- [ ] Debian package builds without errors (`python tools/build.py deb`)
- [ ] RPM package builds without errors (`python tools/build.py rpm`)
- [ ] `ruff check src tests` exits 0
- [ ] `pytest -q` all tests pass (or known failures documented)

## Install

- [ ] AppImage: `chmod +x && ./OpenAdminDesk-x86_64.AppImage --version` prints version
- [ ] Deb: `sudo dpkg -i openadmindesk_*.deb && openadmindesk --version` prints version
- [ ] RPM: `sudo rpm -ivh openadmindesk-*.rpm && openadmindesk --version` prints version
- [ ] No missing library errors on first launch

## First Run

- [ ] Application starts without crash
- [ ] Main window shows: activity rail, connection tree, empty tab area
- [ ] "New Session" button opens Session Wizard
- [ ] Session Wizard shows protocol cards: SSH, RDP, Telnet, VNC, Local Shell
- [ ] Can create SSH profile through wizard Save/Finish

## Vault

- [ ] File → Setup Vault → choose master password → vault created
- [ ] File → Unlock Vault → enter password → vault unlocks
- [ ] Vault → Manage Accounts → add/edit/remove accounts
- [ ] Profile Editor references vault accounts (credential selector populated)

## Connect

- [ ] SSH: open profile → trust host key → terminal appears → commands work
- [ ] SFTP: open SFTP from profile → list files → upload/download/delete
- [ ] RDP: open RDP profile → certificate TOFU dialog → connection (or graceful failure diagnostics)
- [ ] VNC: open VNC profile → connection (or clear error message)
- [ ] Telnet: open Telnet profile → cleartext warning → connection
- [ ] Local Shell: open local shell → commands work

## Import/Export

- [ ] Export profile → JSON file contains no passwords/keys
- [ ] Import profile → loads correctly into tree
- [ ] Import CSV → loads correctly

## Uninstall

- [ ] AppImage: delete file, no residual processes
- [ ] Deb: `sudo dpkg -r openadmindesk` → clean removal
- [ ] RPM: `sudo rpm -e openadmindesk` → clean removal

## Security

- [ ] No secrets in `~/.local/share/openadmindesk/profiles.db` (password columns NULL for vault-linked profiles)
- [ ] `~/.config/openadmindesk/rdp_known_certs.json` permissions 0600
- [ ] Exported profiles contain no plaintext passwords or private key passphrases
- [ ] `tools/build.py` produces packages without secrets

## Sign-Off

| Check | Date | Tester | Result |
|-------|------|--------|--------|
| Build | | | |
| Install | | | |
| First Run | | | |
| Vault | | | |
| Connect | | | |
| Import/Export | | | |
| Uninstall | | | |
| Security | | | |
