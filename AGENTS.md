# Agent Operating Rules for OpenAdminDesk

These rules are mandatory for every coding agent working in this repository.
They are optimized for simple LLMs with limited planning ability.

## Start Here

1. Read this file completely.
2. Read `docs/agent/CONTEXT_PACK.md`.
3. Read only the documents needed for the current task.
4. Before editing code, write a short plan in `docs/WORKLOG.md`.
5. Make small changes. Do not rewrite large areas unless a task explicitly asks.
6. After each change, run the smallest useful verification.
7. Update `docs/WORKLOG.md` with what changed and how it was checked.
8. Check `docs/ACCEPTANCE_CRITERIA.md` before reporting completion.

## Project Goal

Build a modern Linux desktop application that makes SSH, SFTP, tunnels,
credential management, and remote graphical application forwarding convenient
from one scalable GUI.

Do not copy proprietary branding, artwork, text, binaries, screenshots, color
identity, icons, exact layouts, or trade dress from other products. The project
can be functionally inspired by common remote administration workflows, but it
must be original open source software.

Do not read proprietary reference archives unless the user explicitly asks for a
separate legal/workflow analysis. Never copy anything from those archives into
this repository.

## Engineering Rules

- Prefer simple, boring, maintainable code.
- Follow `docs/IMPLEMENTATION_RULES.md`.
- Keep files small and focused.
- Keep UI code separated from SSH/SFTP/vault logic.
- Build command invocations with argument lists, never shell strings.
- Keep profile and vault formats documented.
- Add tests for behavior, not implementation details.
- Keep secrets out of git. Never commit private keys, passwords, tokens, or
  real customer host data.
- If a requirement is unclear, add a question to `docs/WORKLOG.md` and choose
  the safest small step.

## Product Priorities

1. Scalable main window with connection tree and tabbed workspace.
2. SSH profile model and safe OpenSSH command construction.
3. Terminal tab backend abstraction.
4. SFTP browser connected to an SSH profile.
5. Credential vault with master password.
6. Tunnels and X11 forwarding workflows.
7. Packaging and release automation.

## Recommended Task Size

A good task should fit into one of these shapes:

- Add one UI screen skeleton.
- Add one profile field and its validation.
- Add one command wrapper.
- Add one test file.
- Improve one document section.

Avoid tasks that say "build the whole app", "implement all SSH", "finish UI",
or "make it like product X".

## Verification Rules

Use the most relevant check available:

- Documentation only: review changed Markdown and links.
- Python code: run unit tests and lint/type checks when configured.
- UI code: run the app locally and capture the observed behavior in the log.
- Packaging code: build the package in a clean environment before marking done.

If a check cannot be run, write the reason in `docs/WORKLOG.md`.

## Definition of Done

A task is done only when:

- The requested behavior or document exists.
- The change is small enough to review.
- Verification was run or a blocker was recorded.
- `docs/WORKLOG.md` was updated.
- Any new follow-up work was added to `docs/ROADMAP.md` or the current task
  file.
- Relevant acceptance criteria were checked.
