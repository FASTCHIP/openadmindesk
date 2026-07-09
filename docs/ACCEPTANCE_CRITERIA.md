# Acceptance Criteria

A task is complete only when all relevant items below are true.

## For Any Task

- The change matches the requested task.
- The change is small enough to review.
- `docs/WORKLOG.md` was updated.
- Verification was run or the blocker was recorded.
- `git status` shows only intentional changes before commit.
- No secrets or proprietary assets were added.

## For Code Tasks

- Tests were added or an explicit reason was recorded.
- Existing tests pass when dependencies are available.
- Public behavior is documented when it affects users or agents.
- New dependencies are justified.
- Errors are handled with useful messages.

## For UI Tasks

- Layout uses Qt layout managers.
- Text does not overlap at 1366x768.
- HiDPI behavior was considered.
- New controls have clear labels or tooltips.
- Empty, loading, success, and failure states are handled when relevant.

## For SSH/SFTP/Tunnel Tasks

- Commands are built as argument lists.
- No secret is passed through argv or logs.
- Ports are validated.
- Host key behavior is not weakened silently.
- Destructive remote file actions require confirmation.

## For Vault Tasks

- Master password is never stored.
- Fake secrets are used in tests.
- Wrong password behavior is tested.
- Plaintext secret is not present in serialized storage.

