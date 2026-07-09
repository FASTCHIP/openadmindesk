# Implementation Rules

These rules keep implementation predictable for small LLM agents.

## Change Size

- One task should change one feature area.
- Prefer small files with clear names.
- Do not combine UI redesign, storage migration, and protocol work in one
  change.
- Update `docs/WORKLOG.md` for every task.

## Layering

- UI code lives under `src/openadmindesk/ui/`.
- Domain logic lives under `src/openadmindesk/core/`.
- Platform and dependency checks live under `src/openadmindesk/platform/`.
- UI widgets call core services through small interfaces.
- Core services must not import Qt widgets.

## Subprocesses

- Build all commands as argument lists.
- Do not use `shell=True` unless a decision is recorded in
  `docs/DECISIONS.md`.
- Never pass passwords or private-key passphrases through command arguments.
- Capture stderr and show a safe user-facing summary.

## Dependencies

- Prefer mature Linux-native open source components.
- Add a dependency only when it removes meaningful complexity.
- Record important dependency choices in `docs/DECISIONS.md`.
- Keep optional platform features behind capability checks.

## Security

- Do not log secrets.
- Do not commit real hostnames, credentials, keys, tokens, or customer data.
- Do not read or copy proprietary reference archives during implementation.
- Confirm destructive remote file operations.

## UI

- Use Qt layout managers, not absolute positioning.
- Keep text readable at 1366x768 and HiDPI scaling.
- Build reusable widgets for connection tree, tabs, profile editor, vault, SFTP,
  and tunnels.
- Do not copy proprietary layouts pixel-for-pixel.

