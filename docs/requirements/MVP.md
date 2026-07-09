# MVP Requirements

The MVP must prove the main product shape: connection tree, tabs, SSH, SFTP,
credentials, and remote graphical app forwarding. Implementation can be staged,
but the architecture must not block these capabilities.

## Functional Requirements

### Profiles

- Create, edit, delete, duplicate, import, and export SSH profiles.
- Required fields: name, host, username, port.
- Optional fields: identity file, account reference, jump host, working
  directory, environment variables, labels, notes, X11 forwarding, compression,
  keepalive, proxy command, and local/remote/dynamic forwards.
- Store profile metadata in SQLite.
- Store secrets only in the encrypted credential vault.

### Connection Tree

- Show folders and saved connections in a left tree.
- Support search/filter.
- Support drag-and-drop organization later; MVP can expose move actions.
- Show protocol and status icons.

### Terminal Workspace

- Open a profile in a terminal tab.
- Rename tabs.
- Close tabs safely.
- Support multiple tabs and future split panes without redesign.
- Show connection status.
- Reconnect a closed or failed session.

### File Transfer

- Open an SFTP browser for a profile.
- List remote directory contents.
- Upload and download files.
- Create and delete directories with confirmation.
- Do not delete recursively in MVP unless explicitly implemented with tests.

### Port Forwarding

- Save local forward profiles.
- Save remote forward profiles.
- Save dynamic SOCKS forward profiles.
- Start and stop a forward.
- Show active forward status.

### Credentials

- Create a master password on first vault use.
- Unlock the vault for the current session.
- Save account records: username, password, private-key passphrase, notes.
- Link an account record to one or more SSH profiles.
- Never display a secret unless the user explicitly requests reveal.

### X11 and Remote GUI

- Expose SSH X11 forwarding options in profiles.
- Detect whether local X11/Xwayland support is available.
- Provide a launch action for a remote GUI command through an SSH profile.
- Show clear errors when X11 forwarding cannot be started.

### Snippets

- Save named command snippets.
- Insert a snippet into the active terminal.
- Keep snippets as local plain files.

## Non-Functional Requirements

- The app must not require root privileges to run.
- All subprocess calls must use argument lists, not shell-concatenated strings.
- The UI must remain responsive while SSH/SFTP commands run.
- Errors must be visible and actionable.
- The UI must scale cleanly on HiDPI displays.
- The main window must be useful at 1366x768 and comfortable on large displays.

## Security Requirements

- Never log passwords, tokens, private keys, or full command lines containing
  secrets.
- Identity files are referenced by path, not copied into the project data.
- Host key warnings must not be silently ignored.
- Any destructive remote file operation requires confirmation.
- The master password must never be stored.

