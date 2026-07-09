# OpenAdminDesk

OpenAdminDesk is a modern open source remote administration workbench for Linux
desktops.

The goal is to provide the same level of everyday convenience that experienced
administrators expect from mature remote terminal suites: a connection tree,
tabbed terminals, SSH and SFTP workflows, credential management, port
forwarding, and remote graphical application forwarding. OpenAdminDesk must be
an original product, not a clone of any proprietary application.

## Product Direction

- Native Linux desktop application for Ubuntu, Debian, Fedora, Rocky Linux,
  AlmaLinux, and other RHEL-like systems.
- Modern scalable GUI with a connection tree, tabs, split panes, toolbars,
  status indicators, and keyboard shortcuts.
- First-class SSH profiles with important OpenSSH options exposed through a
  friendly interface.
- SFTP file manager integrated with the active SSH session.
- Credential and account manager protected by a master password.
- SSH tunnels and X11 forwarding for remote graphical applications.
- Packaging for AppImage first, then `.deb` and `.rpm`.

## Legal Boundary

The project may be inspired by common remote administration workflows, but it
must not copy proprietary code, icons, screenshots, text, branding, color
identity, or pixel-perfect layouts.

Reference materials can be used only to understand user workflows at a high
level. Do not import, unpack, or reverse engineer proprietary binaries during
implementation work.

## Proposed Stack

- Language: Python 3.12+
- UI: PySide6 / Qt 6
- Terminal: libvte/PTY backend where available, with an abstraction for fallback
  implementations.
- SSH: OpenSSH command-line client first, wrapped safely with argument lists.
- SFTP: OpenSSH `sftp` first for MVP; async library integration can be evaluated
  after workflows are stable.
- Credentials: local encrypted vault, master password, Argon2id KDF,
  AES-256-GCM encryption.
- Storage: SQLite for profiles and metadata; encrypted secret blobs for
  credentials.
- Packaging: AppImage first, then Debian and RPM packages.

## Repository Map

- `AGENTS.md` - mandatory operating rules for coding agents.
- `docs/PROJECT_BRIEF.md` - product definition and constraints.
- `docs/PRODUCT_REQUIREMENTS.md` - full product capabilities and UX targets.
- `docs/DATA_MODEL.md` - stable domain object shapes.
- `docs/SSH_OPTIONS.md` - OpenSSH option mapping.
- `docs/VAULT_SPEC.md` - credential vault design.
- `docs/UI_SPEC.md` - detailed UI structure.
- `docs/DEVELOPMENT_ENV.md` - setup and verification commands.
- `docs/TEST_PLAN.md` - test strategy.
- `docs/ACCEPTANCE_CRITERIA.md` - task completion rules.
- `docs/requirements/MVP.md` - first deliverable requirements.
- `docs/ROADMAP.md` - staged implementation plan.
- `docs/ARCHITECTURE.md` - technical design notes.
- `docs/UI_UX.md` - interface principles and screen layout.
- `docs/SECURITY_MODEL.md` - credential and secret-handling design.
- `docs/agent/` - compact context and task templates for small models.
- `docs/WORKLOG.md` - chronological work log.
- `docs/DECISIONS.md` - architecture decision records.
- `src/` - application source code.
- `tests/` - automated tests.
- `tools/` - developer scripts.

## First Agent Command

When a new agent starts, give it this instruction:

```text
Read AGENTS.md and docs/agent/CONTEXT_PACK.md. Then pick the next unchecked
task from docs/ROADMAP.md. Make a small change, update docs/WORKLOG.md, and
run the relevant verification command.
```
