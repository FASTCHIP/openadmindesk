# Agent Context Pack

This is the short context file for simple LLM agents.

## One-Sentence Goal

Build OpenAdminDesk: an open source Linux desktop workbench with a scalable
connection tree, tabbed SSH terminals, SFTP, credential vault, tunnels, and X11
remote GUI workflows.

## Current Priority

Follow `docs/ROADMAP.md`. The next unfinished phase is the current priority.

## Hard Boundaries

- Do not copy proprietary product names, icons, screenshots, text, or code.
- Do not read proprietary reference archives during implementation tasks.
- Do not commit secrets.
- Do not implement huge features in one step.
- Do not use shell string concatenation for commands.
- Do not make destructive remote file operations without confirmation.

## Useful Documents

- Product: `docs/PROJECT_BRIEF.md`
- Product requirements: `docs/PRODUCT_REQUIREMENTS.md`
- MVP: `docs/requirements/MVP.md`
- Architecture: `docs/ARCHITECTURE.md`
- UI/UX: `docs/UI_UX.md`
- Security: `docs/SECURITY_MODEL.md`
- Roadmap: `docs/ROADMAP.md`
- Work journal: `docs/WORKLOG.md`
- Task format: `docs/agent/TASK_TEMPLATE.md`

## Default Workflow

1. Pick one unchecked roadmap task.
2. Copy `docs/agent/TASK_TEMPLATE.md` into a temporary note or issue.
3. Write a tiny plan in `docs/WORKLOG.md`.
4. Edit only the files needed for that task.
5. Run the smallest useful check.
6. Update `docs/WORKLOG.md`.

## Current Stack Choice

- Python 3.12+
- PySide6 / Qt 6
- System OpenSSH tools first
- SQLite profile metadata
- Encrypted credential vault with master password
- AppImage first, then deb/rpm

