# Decisions

Record important architecture and product decisions here.

## 2026-07-09 - Product name is OpenAdminDesk

Decision: Use OpenAdminDesk as the initial project name.

Reason: The name describes the product without borrowing proprietary branding.

Consequences:

- Package, config, and data paths should use `openadmindesk`.
- The name can still change before the first public release if needed.

## 2026-07-09 - Start with Python and PySide6

Decision: Use Python 3.12+ and PySide6 for the initial desktop app.

Reason: The project is intended for agent-driven development on simple LLMs.
Python and Qt reduce implementation friction and make the code easier to
inspect and modify while still supporting a modern native Linux GUI.

Consequences:

- The first MVP can be built faster.
- Packaging must handle Python dependencies carefully.
- Performance-sensitive pieces can be rewritten later if needed.

## 2026-07-09 - Use system OpenSSH first

Decision: Use system `ssh`, `sftp`, and `scp` commands before adopting a Python
SSH protocol library.

Reason: OpenSSH is mature, secure, widely installed, and supports real-world
configuration such as keys, agents, jump hosts, host key checking, port
forwarding, and X11 forwarding.

Consequences:

- Subprocess management must be clean and well tested.
- UI code must not block while subprocesses run.
- Advanced protocol-level features may require a library later.

## 2026-07-09 - Do not implement an X server from scratch in MVP

Decision: The MVP will orchestrate existing local X11/Xwayland support and SSH
X11 forwarding instead of implementing a new X server.

Reason: X server implementation is complex and not a good first task for a
small LLM agent. Administrators mainly need a reliable workflow, clear
dependency checks, and good errors.

Consequences:

- The X11 manager must detect local support.
- Remote GUI launch is built on OpenSSH `-X`/`-Y`.
- Bundling or managing an X server helper can be evaluated later.

## 2026-07-11 - Stabilize on Paramiko/pyte-first terminal architecture

Decision: During stabilization, keep the current SSH terminal architecture: `SSHTerminalBackend` uses Paramiko for SSH channels and `TerminalWidget` uses a custom pyte-based renderer. Treat the older system OpenSSH/VTE-first direction as superseded for the current prototype.

Reason: The codebase already has working Paramiko SSH/SFTP modules, a pyte renderer, UI integration, and tests around those pieces. Switching to OpenSSH/VTE now would multiply moving parts before the repository, security, test, and threading baselines are stable.

Consequences:

- `TerminalBackend` implementations are profile-bound objects; `connect()` uses the configured profile rather than receiving host/port/password parameters.
- Paramiko remains the SSH/SFTP library until a later decision record explicitly replaces it.
- The pyte terminal is the supported renderer for this prototype; unsupported terminal behavior must be captured as tests or documented gaps.
- OpenSSH/VTE can still be revisited later for terminal fidelity, host platform integration, or system SSH config parity.
- Phase 4 threading work must wrap Paramiko channel operations with Qt-safe workers/signals rather than assuming subprocess/VTE callbacks.


## 2026-07-11 - SFTP browser uses a separate Paramiko session for now

Decision: Keep the SFTP browser on a separate `SftpBackend` connection during stabilization instead of trying to reuse the active SSH terminal channel.

Reason: The current SSH terminal backend owns an interactive Paramiko channel optimized for terminal I/O, while the SFTP browser has independent async file operations and lifecycle. Sharing a transport can be revisited after Phase 4 worker/thread boundaries are clean.

Consequences:

- SFTP may prompt/connect separately from an SSH terminal tab.
- Profile and credential handling must remain consistent so both sessions use the same metadata and vault references.
- A future optimization may share a Paramiko transport if lifecycle, host-key, cancellation, and close semantics are tested.

## 2026-07-14 - Keep legacy plaintext secret columns in current schema

Decision: Retain the existing `password`, `private_key_passphrase`, and
`rdp_gateway_password` columns in the `profiles` SQLite table.  All new saves
and the compensated secret migration (Phase 9.6c) write SQL `NULL` into those
columns; legacy rows remain readable for backward-compatible migration.  Do
not drop the columns until all of the following are true:
- a versioned schema migration mechanism exists,
- adoption evidence shows no pre-migration profiles remain in active databases,
- a tested rollback path exists,
- the format version is bumped.

Reason: Dropping columns early would silently destroy data for users who have
not yet run the migration tool.  Keeping the columns allows safe partial
adoption: a user can migrate one profile at a time, and the old column values
remain visible for comparison until the user explicitly confirms removal.

Consequences:
- The `ProfileStore` row-to-profile mapping and column count (33) are stable.
- No schema migration is required for this phase.
- The migration tool (`migrate_profile_secrets.py`) reads legacy columns,
  migrates to vault, and writes NULL — making the profile a non-migrated
  column has no value.
- A future major format version may drop the columns after confirming no
  legacy rows remain.
- This decision is revisited in Phase 9.6d and recorded here for permanent
  reference.
