# Roadmap

Agents should complete tasks from top to bottom unless the user gives a
different priority.

## Phase 0 - Project Groundwork

- [x] Create repository structure for agent-driven development.
- [x] Define product brief, MVP, architecture, worklog, and task template.
- [x] Choose initial project name: OpenAdminDesk.
- [x] Initialize git in `/ai/openadmindesk`.
- [ ] Add full GPLv3-or-later license text.
- [ ] Add code of conduct and contribution guide.

## Phase 1 - Application Skeleton

- [ ] Create Python package layout under `src/`.
- [ ] Add `pyproject.toml`.
- [ ] Add a minimal PySide6 main window.
- [ ] Add basic unit test setup.
- [ ] Add developer run command.
- [ ] Add dependency check script for Linux desktops.

## Phase 2 - Main Window and Navigation

- [ ] Build scalable main window shell.
- [ ] Add connection tree component.
- [ ] Add tabbed workspace component.
- [ ] Add quick connect toolbar.
- [ ] Add status bar and connection event area.

## Phase 3 - Profiles

- [ ] Implement profile data model.
- [ ] Implement profile validation.
- [ ] Implement SQLite profile store.
- [ ] Add profile list UI.
- [ ] Add profile editor UI.
- [ ] Add import/export.

## Phase 4 - SSH Terminal Sessions

- [ ] Define terminal backend interface.
- [ ] Implement first working terminal backend.
- [ ] Open SSH profile in a tab.
- [ ] Show connection status.
- [ ] Add reconnect action.
- [ ] Add safe OpenSSH option mapping.

## Phase 5 - Credential Vault

- [ ] Define account model.
- [ ] Define vault file/table format.
- [ ] Implement master password setup and unlock.
- [ ] Implement Argon2id key derivation.
- [ ] Implement AES-256-GCM secret encryption.
- [ ] Add account manager UI.

## Phase 6 - SFTP

- [ ] Define remote file model.
- [ ] Implement directory listing.
- [ ] Implement upload.
- [ ] Implement download.
- [ ] Add file browser UI.

## Phase 7 - Tunnels, X11, and Snippets

- [ ] Implement tunnel profile model.
- [ ] Start and stop local forwards.
- [ ] Start and stop remote forwards.
- [ ] Start and stop dynamic SOCKS forwards.
- [ ] Detect local X11/Xwayland support.
- [ ] Launch remote GUI command with SSH X11 forwarding.
- [ ] Implement snippet store.
- [ ] Insert snippets into active terminal.

## Phase 8 - Packaging

- [ ] Document Ubuntu dependencies.
- [ ] Document RHEL-family dependencies.
- [ ] Build AppImage.
- [ ] Build `.deb`.
- [ ] Build `.rpm`.
- [ ] Smoke test install and launch.
