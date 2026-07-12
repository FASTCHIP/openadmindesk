# Operating Manual for Small Agents

## How to Pick Work

Choose the first unchecked item in `docs/AUDIT_REMEDIATION_PLAN.md` unless the
user says otherwise.

If the task is too large, split it into smaller checklist items in that file
before coding.

## How to Read

Read in this order:

1. `AGENTS.md`
2. `docs/agent/CONTEXT_PACK.md`
3. The active task in `docs/AUDIT_REMEDIATION_PLAN.md`
4. Only the code/docs named by the task

Do not read every document by default. That wastes context and causes drift.

## How to Edit

- Make one coherent change per turn.
- Prefer fixing proven runtime/lint/test failures before refactoring.
- Keep UI code in `ui/` and security/storage logic in `core/`.
- Use Qt signals or main-thread callbacks for UI updates from workers.
- Keep credential material out of profile JSON, SQLite profile rows, logs, and tests.
- Add or update focused tests when behavior changes.

## How to Report

At the end of each task, report:

- changed files,
- verification command,
- result,
- remaining risk,
- next suggested task.

## Common Mistakes to Avoid

- Following old audit documents instead of `docs/AUDIT_REMEDIATION_PLAN.md`.
- Marking a feature complete because a file exists.
- Blocking the UI thread with network, SSH, SFTP, or subprocess work.
- Updating widgets from background threads.
- Treating warning-only SSH host-key policy as secure.
- Passing passwords through process arguments.
- Exporting or syncing plaintext credentials.
- Adding dependencies without updating `pyproject.toml`, lockfile, and docs.
