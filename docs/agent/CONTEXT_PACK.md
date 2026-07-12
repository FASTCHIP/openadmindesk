# Agent Context Pack

This is the short context file for simple LLM agents.

## One-Sentence Goal

Build OpenAdminDesk: an original open source remote administration workbench with
a connection tree, tabbed terminals, SSH/SFTP workflows, credential vault,
tunnels, and remote GUI helpers.

## Current Priority

Follow `docs/AUDIT_REMEDIATION_PLAN.md` first. The project is in stabilization,
not feature expansion.

Active order:

1. Repository hygiene and secret/runtime file cleanup.
2. Lint/runtime errors that break imports or UI clicks.
3. Test harness stability.
4. Secret storage redesign.
5. Qt threading boundaries.
6. Terminal/SSH architecture decision and implementation.

## Hard Boundaries

- Do not copy proprietary product names, icons, screenshots, text, code, binaries, or exact layouts.
- Do not read proprietary reference archives during implementation tasks.
- Do not commit secrets, local databases, vault files, or sync config.
- Do not store new credentials in plaintext profile fields.
- Do not use shell string concatenation for commands.
- Do not update Qt widgets from worker threads.
- Do not make destructive file operations without a backup or explicit task instruction.
- Do not add large features while baseline lint/tests/security are broken.

## Source Of Truth

Use these documents in this order:

1. `AGENTS.md` - mandatory rules.
2. `docs/AUDIT_REMEDIATION_PLAN.md` - current task backlog.
3. `docs/WORKLOG.md` - what was actually done.
4. `docs/DECISIONS.md` - accepted architecture decisions.
5. Code and tests - final truth when docs disagree.

Useful stable references:

- Product: `docs/PROJECT_BRIEF.md`
- Requirements: `docs/PRODUCT_REQUIREMENTS.md`
- Implementation rules: `docs/IMPLEMENTATION_RULES.md`
- Data model: `docs/DATA_MODEL.md`
- Security: `docs/SECURITY_MODEL.md`
- Vault: `docs/VAULT_SPEC.md`
- UI: `docs/UI_SPEC.md`, `docs/UI_UX.md`
- Development: `docs/DEVELOPMENT_ENV.md`
- Tests: `docs/TEST_PLAN.md`
- Acceptance: `docs/ACCEPTANCE_CRITERIA.md`

## Default Workflow

1. Pick one unchecked task from `docs/AUDIT_REMEDIATION_PLAN.md`.
2. Read only the files named in that task plus nearby code.
3. Add a short plan entry to `docs/WORKLOG.md`.
4. Edit only the files needed for that task.
5. Run the smallest useful check.
6. Update `docs/WORKLOG.md` with result and remaining risk.
7. Report changed files, verification, and next task.

## Current Stack Reality

- Python 3.12+
- PySide6 / Qt 6
- Current terminal prototype: custom `pyte` renderer
- Current SSH/SFTP prototype: Paramiko modules
- Architecture decision now stabilizes on Paramiko/pyte-first for the current prototype
- SQLite profile metadata
- Encrypted vault exists, but profile plaintext secret storage must be removed
- AppImage/deb/rpm packaging exists only as unverified tooling
