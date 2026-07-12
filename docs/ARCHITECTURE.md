# Architecture

## Design Principle

The first version should be a reliable orchestrator around proven Linux tools,
not a complete reimplementation of SSH, SFTP, terminal emulation, X servers, and
secrets management.

## High-Level Components

- UI shell: main window, navigation, tabs, dialogs.
- Connection tree: folders, search, profile actions.
- Profile store: validate, save, import, export.
- Credential vault: master password, account records, encrypted secrets.
- SSH terminal backend: Paramiko channel wrapped by `SSHTerminalBackend`.
- Terminal renderer: custom `pyte` screen rendered by Qt `TerminalWidget`.
- SFTP backend: Paramiko SFTP client with explicit TOFU host-key policy.
- Tunnel manager: starts and tracks SSH port-forwarding subprocesses.
- X11 manager: detects local X support and launches remote GUI commands.
- Snippet store: local reusable command snippets.
- Platform layer: paths, dependencies, packaging differences.

## Suggested Module Layout

```text
src/openadmindesk/
  app.py
  ui/
    main_window.py
    connection_tree.py
    profile_editor.py
    account_manager.py
    terminal_tabs.py
    file_browser.py
    tunnel_panel.py
    x11_panel.py
  core/
    profiles.py
    accounts.py
    vault.py
    ssh_runner.py
    sftp_runner.py
    tunnel_manager.py
    x11_manager.py
    snippets.py
    paths.py
  platform/
    detect.py
    dependencies.py
tests/
  test_profiles.py
  test_ssh_runner.py
  test_vault.py
```

## Storage

Use user-local directories:

```text
~/.config/openadmindesk/
~/.local/share/openadmindesk/
```

Use SQLite for profile metadata and UI organization:

```text
~/.local/share/openadmindesk/openadmindesk.sqlite3
```

Use a separate encrypted vault file or encrypted SQLite table for secrets. The
format must be documented before production use.

## Subprocess Safety

Always use argument lists:

```python
subprocess.Popen(["ssh", "-p", str(port), f"{user}@{host}"])
```

Do not build shell strings:

```python
subprocess.Popen(f"ssh -p {port} {user}@{host}", shell=True)
```

## Terminal Embedding Strategy

Current decision: Paramiko/pyte-first for the stabilization prototype.

```text
backend = SSHTerminalBackend(profile)
backend.connect(on_output=terminal.feed)
```

`TerminalBackend` instances are profile-bound. The UI should not pass host, port,
or credentials into `connect()`; those belong in `Profile` plus vault-backed
credential references.

Known gaps for the pyte renderer must be tracked with focused tests before
claiming broad terminal compatibility: alternate screen behavior, mouse reporting,
bracketed paste, truecolor, resize edge cases, and large scrollback performance.

## X11 Forwarding Strategy

OpenAdminDesk should not implement an X server from scratch in the MVP.
Instead:

1. Detect whether X11 or Xwayland is available locally.
2. Start SSH sessions with `-X` or `-Y` only when requested.
3. Provide remote command launch actions for GUI apps.
4. Later evaluate bundling or managing a local X server helper where it is
   legally and technically practical.

## Error Handling

Every operation should return either:

- success with result data, or
- failure with a short user-facing message and a longer debug message.

Do not hide subprocess stderr. Capture it and show a safe summary.

