# Product Requirements

## Vision

OpenAdminDesk should feel like a polished daily workstation for Linux
administrators: fast to open, easy to scan, comfortable on HiDPI displays, and
powerful enough for many servers, accounts, tabs, transfers, tunnels, and
remote GUI launches.

## Primary Workflows

### Manage Connections

- Organize hosts in a left connection tree.
- Group by folder, customer, environment, project, tag, or protocol.
- Search connections quickly.
- Open a connection by double-clicking or keyboard action.
- Duplicate, export, import, and edit profiles.

### Work in Tabs

- Open multiple SSH sessions in tabs.
- Rename, reorder, detach later, and close tabs safely.
- Show session state and host identity clearly.
- Keep the UI useful at small laptop sizes and large monitors.

### Use SSH Well

- Support common OpenSSH options: port, user, identity file, jump host,
  compression, keepalive, host key behavior, agent forwarding, X11 forwarding,
  local forwards, remote forwards, and dynamic forwards.
- Prefer OpenSSH for real-world compatibility.
- Never hide host key warnings silently.

### Transfer Files

- Browse remote files over SFTP.
- Upload, download, create folder, rename, and delete with confirmation.
- Preserve permissions and timestamps where practical.
- Show transfer progress and errors.

### Manage Credentials

- Store accounts separately from host profiles.
- Protect the vault with a master password.
- Support password, private-key passphrase, and notes.
- Allow the user to reveal or copy a secret only through explicit actions.
- Lock the vault manually and after idle timeout later.

### Launch Remote GUI Apps

- Detect local X11/Xwayland availability.
- Enable SSH X11 forwarding per profile.
- Launch a remote GUI command through an existing SSH profile.
- Explain missing dependencies clearly.

## Design Requirements

- Modern but work-focused visual style.
- Dense, readable layout rather than marketing-style screens.
- Scalable fonts and icons through Qt high-DPI support.
- Keyboard-friendly navigation.
- No pixel-perfect copy of proprietary products.

## Release Goals

- AppImage as first distributable artifact.
- Debian package.
- RPM package.
- Clear dependency checks for terminal, SSH, SFTP, X11, and FreeRDP if RDP is
  added later.

