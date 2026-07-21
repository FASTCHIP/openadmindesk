# Roadmap

Agents should complete tasks from top to bottom unless the user gives a different
priority.

## Current Development Mode

Stabilization is reopened for Phase 11 until real GitHub CI is green. `docs/AUDIT_REMEDIATION_PLAN.md`
remains authoritative for stabilization; this roadmap is for product work afterward.

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

## Detailed Implementation Roadmap

### General Engineering Rules
- **Built-in Utility Rule**: User-facing workflows must be implemented inside the application using Python/platform APIs or packaged open-source libraries; no dependency on launching separately installed CLI tools for core functionality; never build shell strings; privileged capabilities must fail safely/explain limits. Libraries like FreeRDP may be embedded/packaged with license compliance; do not implement complex protocols insecurely from scratch.
- **MobaXterm Guardrail**: Approximate concrete admin workflows/quality only; never copy branding, proprietary assets/text/screenshots/exact layout/trade dress. Do not claim parity.
- **Pass Boundary Rule**: Each implementation/test pass changes no more than 3 non-doc implementation/test files; documentation/worklog changes are performed in separate passes and explicitly named.

### Implementation Directions

#### 1. CI/Version/Release Stabilization
- **Goal**: Zero-failure CI pipeline and immutable versioning.
- **Constraints**: Must not rewrite existing tags (v0.1.3).
- **Passes**:
  - Pass 1: Centralize version in one source of truth.
  - Pass 2: Harden CI workflow (actionlint, Ruff coverage).
  - Pass 3: Verify GitHub CI green run.
- **Acceptance**: GitHub CI green, version consistent.
- **Verification**: GitHub Actions run status.

#### 2. Terminal Fidelity and Split/MultiExec Quality
- **Goal**: Professional-grade terminal experience.
- **Constraints**: Paramiko/pyte baseline.
- **Passes**:
  - Pass 1: Fix escape sequence handling and terminal resizing.
  - Pass 2: Improve MultiExec broadcast reliability and UI feedback.
  - Pass 3: Implement split-pane workspace layout.
- **Acceptance**: No visual glitches on resize, MultiExec works for 10+ targets.
- **Verification**: Manual smoke tests, targeted pytest.

#### 3. Integrated SFTP Workflow
- **Goal**: Seamless file management integrated with sessions.
- **Constraints**: Vault-backed credentials.
- **Passes**:
  - Pass 1: Improve SFTP browser navigation and filtering.
  - Pass 2: Enhance transfer queue with priority and scheduling.
  - Pass 3: Implement integrated remote-to-remote transfer.
- **Acceptance**: Stable transfers, intuitive UI.
- **Verification**: `tests/test_sftp_backend.py`, `tests/test_transfer_queue.py`.

#### 4. Scalable Session Manager
- **Goal**: Manage thousands of sessions without UI lag.
- **Constraints**: SQLite backend.
- **Passes**:
  - Pass 1: Implement virtualized connection tree.
  - Pass 2: Add advanced grouping and tagging logic.
  - Pass 3: Optimize search and filter performance.
- **Acceptance**: Tree remains responsive with 1000+ items.
- **Verification**: Performance benchmarks, `tests/test_connection_tree.py`.

#### 5. Built-in Network and Admin Utilities
- **Goal**: Provide essential tools without external dependencies.
- **Constraints**: Built-in Utility Rule.
- **Passes**:
  - Pass 1: Implement Ping/Traceroute/DNS lookup.
  - Pass 2: Add port scanner and service detector.
  - Pass 3: Implement basic network topology visualizer.
- **Acceptance**: Tools work across OSs, no shell-string injection.
- **Verification**: Targeted unit tests for each utility.

#### 6. Embedded RDP/VNC/X11 Workflows
- **Goal**: High-performance embedded remote GUI.
- **Constraints**: FreeRDP/LibVNC integration.
- **Passes**:
  - Pass 1: Optimize frame rendering and input latency.
  - Pass 2: Implement advanced RDP features (multimon, clipboard).
  - Pass 3: Standardize VNC/X11 embedded views.
- **Acceptance**: Fluid GUI experience, no crashes on disconnect.
- **Verification**: `tests/test_rdp_client.py`, manual smoke.

#### 7. Command Palette, Snippets, Macros, Safe Automation
- **Goal**: Power-user productivity tools.
- **Constraints**: Safe automation (no arbitrary shell execution).
- **Passes**:
  - Pass 1: Implement Command Palette (Ctrl+Shift+P).
  - Pass 2: Expand snippet library with dynamic variables.
  - Pass 3: Implement safe macro recorder/player.
- **Acceptance**: Fast access to all app functions, safe macro execution.
- **Verification**: `tests/test_snippets.py`, manual smoke.

#### 8. Evidence, Packaging, Release Quality
- **Goal**: Production-ready distribution.
- **Constraints**: Clean-env builds.
- **Passes**:
  - Pass 1: Automate release artifact generation.
  - Pass 2: Create comprehensive GUI smoke evidence.
  - Pass 3: Final security audit and sign-off.
- **Acceptance**: Verified artifacts on GitHub Releases.
- **Verification**: `tools/build.py`, `docs/GUI_SMOKE_EVIDENCE.md`.

### Immediate Next Implementation Order
1. Phase 11: Version centralization.
2. Phase 11: CI workflow hardening.
3. Phase 11: Actual GitHub green run.
4. Direction 2: Terminal fidelity.
