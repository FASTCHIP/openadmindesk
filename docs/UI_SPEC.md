# UI Specification

## Main Window

The first screen is the working application, not a welcome page.

Required regions:

- top toolbar,
- left connection tree,
- central tab workspace,
- bottom status/event area.

The layout must scale from 1366x768 to large HiDPI displays.

## Toolbar

Initial actions:

- new profile,
- quick connect,
- open terminal,
- open SFTP,
- tunnels,
- credential vault lock/unlock,
- settings.

Use icons with tooltips when the icon meaning is not obvious.

## Connection Tree

Tree item types:

- folder,
- SSH profile,
- tunnel group,
- recent session.

Tree behavior:

- double-click opens the default action,
- context menu exposes edit, duplicate, delete, export, open terminal, open SFTP,
- search filters visible items,
- status marker shows disconnected, connecting, connected, failed.

## Tab Workspace

Tab types:

- SSH terminal,
- SFTP browser,
- tunnel monitor,
- settings,
- account manager.

Tab requirements:

- close button,
- rename action,
- connection state indicator,
- no layout jumps when titles change.

## Profile Editor

Sections:

- General: name, folder, tags, notes.
- Connection: host, port, username, account, identity file.
- SSH Options: jump host, compression, keepalive, agent forwarding.
- Tunnels: local, remote, dynamic.
- X11: disabled, untrusted, trusted, remote command.

Validation:

- host is required,
- port must be 1-65535,
- name is required,
- destructive changes require confirmation only when they affect active sessions.

## SFTP Browser

Required controls:

- path bar,
- refresh,
- upload,
- download,
- new folder,
- rename,
- delete with confirmation,
- transfer progress.

## Credential UI

States:

- vault not configured,
- vault locked,
- vault unlocked,
- unlock failed,
- idle timeout locked later.

Secrets are hidden by default. Reveal and copy are explicit actions.

