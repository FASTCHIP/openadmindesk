# Agent Operating Rules for OpenAdminDesk

These rules are mandatory for every coding agent working in this repository.
They are written for small models: read less, change less, verify more.

## Start Here

1. Read this file completely.
2. Read `docs/agent/CONTEXT_PACK.md`.
3. Read `docs/AUDIT_REMEDIATION_PLAN.md` before choosing work.
4. Pick exactly one unchecked task from the active phase unless the user says otherwise.
5. Before editing, add a short plan entry to `docs/WORKLOG.md`.
6. Make a small change. Do not combine unrelated fixes.
7. Run the smallest useful verification.
8. Update `docs/WORKLOG.md` with changed files, command output summary, and remaining risk.
9. Report only what changed, how it was checked, and the next best task.

## Current Project Reality

OpenAdminDesk is not yet a stable product. Treat the current code as a prototype
that needs stabilization before feature expansion.

Known current priorities:

1. Clean git/runtime hygiene and keep secrets out of the repository.
2. Fix lint/runtime errors that prevent reliable execution.
3. Fix the test harness so `pytest` does not enter the real Qt event loop.
4. Move passwords and key passphrases out of plaintext profile storage.
5. Fix Qt threading boundaries for SSH/SFTP/local shell output.
6. Decide and implement the terminal/SSH strategy consistently.

Do not use old audit files as source of truth. The authoritative plan is
`docs/AUDIT_REMEDIATION_PLAN.md`.

## Product Goal

Build an original open source remote administration workbench with a scalable
connection tree, tabbed terminal workspace, SSH/SFTP workflows, credential vault,
tunnels, and remote GUI helpers.

The app may be inspired by common administrator workflows, but it must not copy
proprietary code, branding, artwork, screenshots, text, exact layouts, color
identity, icons, or trade dress from any product.

## Hard Boundaries

- Never commit real passwords, private keys, tokens, real customer host data, or local databases.
- Never store new credentials in `ProfileStore` plaintext fields.
- Never build subprocess commands with shell strings when an argument list works.
- Never update Qt widgets from worker threads; use Qt signals or main-thread callbacks.
- Never mark packaging or security done without running the matching verification.
- Never rewrite large modules as part of a small task.
- Never trust docs over code. If they disagree, record the mismatch and fix the source of truth.

## Repository Map

- `src/openadmindesk/core/` - domain logic, storage, protocol/session backends.
- `src/openadmindesk/ui/` - PySide6 widgets only. UI should orchestrate, not own security logic.
- `src/openadmindesk/platform/` - OS paths and platform helpers.
- `tests/` - automated tests. Keep core tests display-independent.
- `docs/AUDIT_REMEDIATION_PLAN.md` - current stabilization backlog.
- `docs/WORKLOG.md` - chronological work journal.
- `docs/DECISIONS.md` - architecture decisions.
- `docs/agent/` - short instructions for small agents.

## Engineering Rules

- Prefer simple, boring, maintainable code.
- Read nearby code before changing it.
- Keep files small and focused.
- Add or update tests for behavior, not implementation details.
- Keep profile and vault formats versioned and documented.
- Use structured APIs for data formats instead of ad hoc string parsing.
- If a task is too large, split it in `docs/AUDIT_REMEDIATION_PLAN.md` first.
- If a check cannot be run, write the blocker in `docs/WORKLOG.md`.

## Verification Rules

Use the smallest check that proves the task:

- Documentation only: inspect the changed Markdown and links.
- Python syntax/import fix: `python3 -m py_compile <files>` or targeted import.
- Runtime lint fix: `ruff check <files>`.
- Core behavior: targeted `pytest tests/test_*.py -q`.
- Qt behavior: use a headless-safe test harness or document manual launch results.
- Packaging: build in a clean environment before marking done.

## Definition of Done

A task is done only when:

- The requested behavior or document exists.
- The change is small enough to review.
- Verification was run or a blocker was recorded.
- `docs/WORKLOG.md` was updated.
- Follow-up work was added to `docs/AUDIT_REMEDIATION_PLAN.md` when needed.
