# OpenAdminDesk

OpenAdminDesk is an original open source remote administration workbench. The
project aims to provide the everyday convenience administrators expect from a
connection manager: a connection tree, tabbed terminals, SSH/SFTP workflows,
credential management, tunnels, and remote GUI helpers.

## Current Status

This repository is in prototype/stabilization state. It already contains many
features, but the current priority is not more feature work. The next work should
stabilize repository hygiene, tests, secret handling, Qt threading, and the
terminal/SSH architecture.

Authoritative stabilization plan:

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
- Current terminal prototype: `pyte` rendered by a Qt widget
- Current SSH/SFTP prototype: Paramiko-based modules
- Target direction under review: system OpenSSH/VTE-first for Linux compatibility
- Storage: SQLite for profile metadata
- Secrets: encrypted vault, with plaintext profile secrets to be removed during stabilization
- Packaging target: AppImage first, then `.deb` and `.rpm`

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

The current baseline is known to be broken. Start with targeted checks, not a
large refactor:

```bash
ruff check src tests tools
pytest -q
```

If either fails, record the exact failure in `docs/WORKLOG.md` and fix one
failure class at a time.
