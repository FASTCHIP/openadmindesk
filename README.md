# OpenAdminDesk

OpenAdminDesk is an original open source remote administration workbench. The
project aims to provide the everyday convenience administrators expect from a
connection manager: a connection tree, tabbed terminals, SSH/SFTP workflows,
credential management, tunnels, and remote GUI helpers.

## Current Status

This repository has completed its stabilization phase and provides a stable baseline.
The project is feature-complete for its core mission, with available packages
(AppImage, deb, rpm) and a verified test suite.

The stabilization plan is complete:

- `docs/AUDIT_REMEDIATION_PLAN.md`

Do not rely on removed or archived audit notes. If documentation and code
disagree, inspect the code and update the docs.

## Legal Boundary

The project may be inspired by common remote administration workflows, but it
must not copy proprietary code, icons, screenshots, text, branding, color
identity, exact layouts, binaries, or trade dress.

Reference materials may be used only to understand workflows at a high level. Do
not import, unpack, reverse engineer, or copy from proprietary binaries during
implementation work.

## Stack

- Language: Python 3.12+
- UI: PySide6 / Qt 6
- Terminal uses pyte renderer and SSH is Paramiko-based (see docs/DECISIONS.md)
- SSH/SFTP prototype: Paramiko-based modules
- Storage: SQLite for profile metadata
- Secrets: Argon2id v2 vault (plaintext removal complete)
- Packaging target: AppImage first, then `.deb` and `.rpm`

## Features

- Connection tree with folders, favorites, tags, and search
- Tabbed SSH terminals with pyte renderer
- SFTP browser with transfer queue and remote edit safety
- Credential vault (PBKDF2/Argon2id, AES-256-GCM, auto-lock)
- RDP, VNC, Telnet, and Local Shell sessions
- Port forwarding (local, remote, and dynamic SOCKS)
- X11 forwarding
- MultiExec broadcast
- Session Wizard with protocol-specific advanced pages
- Profile import/export (JSON/CSV)
- Central settings (terminal, SFTP, logging)
- AppImage, deb, and rpm packaging

## Installation

Available as AppImage, deb, and rpm packages.
For detailed instructions, see `docs/INSTALL.md`.

### Как получить пакеты (exe, rpm, deb)

Все сборки публикуются на странице [GitHub Releases](https://github.com/FASTCHIP/openadmindesk/releases).

| Формат | Платформа | Файл |
|--------|-----------|------|
| **.exe** | Windows (x64) | `OpenAdminDesk-Setup.exe` |
| **.deb** | Debian / Ubuntu | `openadmindesk_*.deb` |
| **.rpm** | Fedora / RHEL / Rocky / Alma | `openadmindesk-*.rpm` |
| **.AppImage** | Любой Linux (x64) | `OpenAdminDesk-x86_64.AppImage` |

**Установка:**

- **Windows** — запустите `.exe` установщик и следуйте инструкциям мастера.
- **Debian / Ubuntu** — `sudo dpkg -i openadmindesk_*.deb && sudo apt install -f`
- **Fedora / RHEL** — `sudo dnf install openadmindesk-*.rpm`
- **AppImage** — `chmod +x OpenAdminDesk-x86_64.AppImage && ./OpenAdminDesk-x86_64.AppImage`

Подробнее: [`docs/INSTALL.md`](docs/INSTALL.md).

## Repository Map

- `AGENTS.md` - mandatory operating rules for coding agents.
- `docs/AUDIT_REMEDIATION_PLAN.md` - current audit findings and decomposed fix plan.
- `docs/PROJECT_BRIEF.md` - product definition and constraints.
- `docs/PRODUCT_REQUIREMENTS.md` - desired capabilities and UX targets.
- `docs/ARCHITECTURE.md` - architecture direction; verify against code before acting.
- `docs/DATA_MODEL.md` - domain object shapes.
- `docs/SECURITY_MODEL.md` - credential and secret-handling model.
- `docs/VAULT_SPEC.md` - vault design notes.
- `docs/UI_SPEC.md` and `docs/UI_UX.md` - UI structure and principles.
- `docs/DEVELOPMENT_ENV.md` - setup and verification commands.
- `docs/TEST_PLAN.md` - test strategy.
- `docs/ACCEPTANCE_CRITERIA.md` - task completion rules.
- `docs/ROADMAP.md` - high-level product roadmap.
- `docs/WORKLOG.md` - chronological work log.
- `docs/agent/` - compact context and templates for small agents.
- `src/` - application source code.
- `tests/` - automated tests.
- `tools/` - developer scripts.

## First Agent Command

When a new agent starts, give it this instruction:

```text
Read AGENTS.md, docs/agent/CONTEXT_PACK.md, and docs/AUDIT_REMEDIATION_PLAN.md.
Pick the first unchecked task from the active stabilization phase. Make one small
change, update docs/WORKLOG.md, and run the smallest relevant verification.
```

## Quick Verification

The current baseline is functional. For developers, run these commands after any changes to verify the project state:

```bash
ruff check src tests tools
pytest -q
```

For users, verify the installation with:
```bash
openadmindesk --version
```

## Getting Started

Launch the application, set up your credential vault, create a profile, and connect.
For a complete guide, see `docs/USER_GUIDE.md`.

If either command fails, record the exact failure in `docs/WORKLOG.md` and
fix one failure class at a time.
