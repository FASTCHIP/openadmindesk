# Operating Manual for Small Agents

## How to Pick Work

Choose the first unchecked item in `docs/ROADMAP.md` unless the user says
otherwise.

If the task is too large, split it into smaller checklist items before coding.

## How to Edit

- Read nearby code before changing it.
- Keep one concept per file when possible.
- Prefer simple functions with clear names.
- Add tests next to the behavior.
- Update documentation only when behavior or workflow changes.

## How to Report

At the end of each task, report:

- changed files,
- verification command,
- result,
- next suggested task.

## Common Mistakes to Avoid

- Inventing a new architecture without updating `docs/DECISIONS.md`.
- Adding dependencies without documenting why.
- Blocking the UI thread with network or subprocess work.
- Treating user-entered hostnames or paths as trusted shell text.
- Storing real passwords or keys in examples.

