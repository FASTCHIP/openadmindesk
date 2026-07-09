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

