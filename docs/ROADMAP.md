# Roadmap

Agents should complete tasks from top to bottom unless the user gives a different
priority.

## Current Development Mode

The stabilization remediation plan is complete. Keep `docs/AUDIT_REMEDIATION_PLAN.md`
as the closed audit record, and use this roadmap plus `docs/FEATURE_MATRIX.md`
for future feature work.

## Phase 0 - Project Groundwork

- [x] Create repository structure for agent-driven development.
- [x] Define product brief, MVP, architecture, worklog, and task template.
- [x] Choose initial project name: OpenAdminDesk.
- [x] Initialize git in `/ai/openadmindesk`.
- [x] Add detailed agent implementation specs.
- [x] Add full GPLv3-or-later license text.
- [x] Add code of conduct and contribution guide.
- [x] Stabilize repository hygiene and remove runtime/local files from git visibility.

## Phase 1 - Application Skeleton

- [x] Create Python package layout under `src/`.
- [x] Add `pyproject.toml`.
- [x] Add a minimal PySide6 main window.
- [x] Add developer run command.
- [x] Add dependency check script for Linux desktops.
- [x] Restore reliable lint and test baselines.

## Phase 2 - Main Window and Navigation

- [x] Build main window shell with connection tree and tab workspace.
- [x] Add quick connect toolbar.
- [x] Add status bar and connection event area.
- [x] Move long-running session work out of the UI thread.
- [x] Ensure worker output updates widgets only through Qt-safe paths.

## Phase 3 - Profiles And Credentials

- [x] Implement profile data model.
- [x] Implement SQLite profile store.
- [x] Add profile editor and import/export prototypes.
- [x] Add encrypted vault prototype.
- [x] Remove plaintext credential storage from profile rows.
- [x] Make vault format/version/KDF match documented security model.

## Phase 4 - SSH Terminal Sessions

- [x] Implement SSH terminal prototype.
- [x] Open SSH profiles in tabs.
- [x] Show connection status and reconnect action.
- [x] Decide OpenSSH/VTE-first vs Paramiko/pyte-first architecture.
- [x] Align `TerminalBackend` contract with real implementations.

## Phase 5 - SFTP

- [x] Implement SFTP listing/upload/download prototype.
- [x] Add SFTP browser UI prototype.
- [x] Fix host-key policy.
- [x] Decide whether SFTP reuses active SSH session state.
- [x] Add behavior tests for errors, permissions, and remove directory/file flows.

## Phase 6 - Tunnels, X11, RDP, VNC, Local Shell, Snippets

- [x] Implement tunnel profile and manager prototypes.
- [x] Implement X11 helper prototype.
- [x] Implement snippet store/insert prototype.
- [x] Implement RDP/VNC/local shell prototypes.
- [x] Stop passing RDP secrets through argv and add certificate policy.
- [x] Add diagnostics for external process failures.
- [x] Make Session Wizard cover every supported session type.

## Phase 7 - Packaging

- [x] Document Linux dependency direction.
- [x] Create initial build scripts.
- [x] Build AppImage in a clean environment.
- [x] Build `.deb` in a clean environment.
- [x] Build `.rpm` in a clean environment.
- [x] Smoke test install and launch.

## Next Backlog - Post-Stabilization

- [x] Add a real host-key trust-on-first-use UI flow instead of reject-only behavior.
- [x] Add dedicated RDP gateway credentials to the vault account model.
- [ ] Add manual GUI smoke evidence for SSH/SFTP/RDP/VNC/Local Shell on real targets (`docs/GUI_SMOKE_EVIDENCE.md`; blocked on target inventory).
- [x] Add application icons and desktop metadata assets for packaged Linux builds.
- [x] Decide whether to keep Paramiko/pyte long-term or run a separate OpenSSH/VTE spike.

## MobaXterm-Class UX Gap Plan

Use `docs/MOBAXTERM_GAP_PLAN.md` as the next product-quality roadmap after stabilization. The first implementation sprint slices (activity rail/sidebar, attached SFTP/queue, Session Wizard grid/advanced, split workspace, MultiExec, settings skeleton) are already implemented/tested and reflected in `docs/FEATURE_MATRIX.md`.
