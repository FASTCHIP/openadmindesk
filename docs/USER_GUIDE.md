# User Guide

## Quickstart
1. **Launch OpenAdminDesk** — run `openadmindesk` (or double-click AppImage)
2. **Set up vault** — File menu → Setup Vault → choose master password → confirm. This protects your stored credentials.
3. **Unlock vault** — File menu → Unlock Vault → enter master password. Required before saving credentials in profiles.
4. **Create a profile** — Click "New Session" button (or File → New Session). Session Wizard opens:
   - Page 1: Choose protocol (SSH for most servers)
   - Page 2: Host, port, username
   - Page 3 (SSH): Authentication — select credential, or enter password (saved to vault)
   - Advanced pages: compression, keepalive, X11 forwarding, proxy
   - Summary page: review settings, add notes
   - Click Finish
5. **Connect** — Double-click the profile in the connection tree, or right-click → Connect. Terminal tab opens.
6. **Work** — Type commands in the terminal. Use SFTP button in toolbar to browse/transfer files.

## Common Workflows

### Create an SSH session
1. Click "New Session" → select SSH card → Next.
2. Enter host (e.g. `web.example.com`), port (22), username.
3. Authentication page: select a vault account or enter password (saved to vault).
4. Advanced: enable compression for slow links, X11 forwarding for GUI apps.
5. Summary: review settings, click Finish.
6. Double-click the new profile in the connection tree.

### Transfer files via SFTP
1. Connect to an SSH profile.
2. Click the 📁 (SFTP) button in the terminal toolbar — the SFTP sidebar opens.
3. Browse directories in the tree or table view.
4. Upload: drag files from desktop or click Upload.
5. Download: select files, click Download.
6. Edit remote files: double-click → confirm download → edit locally → save to upload back.

### Connect via RDP
1. Create an RDP profile through Session Wizard or Profile Editor.
2. Set Network Level Authentication (NLA) — enabled by default — and Windows domain if needed.
3. Configure TS Gateway for enterprise environments.
4. Open the profile. On first connection, verify the server certificate fingerprint in the TOFU dialog.
5. Use the toolbar: Fullscreen (F11), Ctrl+Alt+Del, Connect/Disconnect.
6. Clipboard sync works automatically — copy local text, paste into remote session.

### Use MultiExec for broadcast commands
1. Open multiple SSH sessions.
2. Click 📢 MultiExec in the toolbar.
3. Check the sessions you want to broadcast to.
4. Type in any checked terminal — keystrokes appear in all selected sessions.
5. Click 🛑 Emergency Stop to clear all selections.

### Organize profiles
1. Right-click the connection tree → New Folder.
2. Drag profiles into folders.
3. Star (★) favorites to pin them at top.
4. Search: type in filter bar; use `tag:production` or `proto:ssh` to filter by tag/protocol.

## Connection Tree
- Organize profiles in folders (right-click tree → New Folder)
- Drag-and-drop profiles into folders
- Search: type in filter bar; supports `tag:xxx` and `proto:xxx` prefixes
- Star (★) favorites appear at top
- Right-click context menu: Connect, Open SFTP, Copy SSH command, Export, Delete

## Terminal Sessions
- Each session opens in a tab
- Resize terminal by resizing window
- Reconnect button (🔄) if connection drops
- Snippets: click Snippets dropdown to insert saved commands
- Attach SFTP: click 📁 to open file browser side panel

## SFTP File Browser
- Browse remote files in tree or table view
- Upload: drag files into browser or click Upload button
- Download: select files, click Download
- Edit remote files: double-click text file → confirm → edit locally → save to upload back (with conflict detection)
- Transfer Queue: click 📋 to see progress, cancel, retry

## Credential Vault
- Vault menu: Setup, Unlock, Lock, Manage Accounts
- Add accounts in Vault → Manage Accounts (SSH keys, passwords, gateway credentials)
- Vault auto-locks after period of inactivity
- Profile editor references vault accounts instead of storing plaintext passwords

## MultiExec (Broadcast)
- Click 📢 MultiExec in toolbar to open panel
- Check boxes next to connected SSH sessions
- Type in any checked terminal — keystrokes broadcast to all selected
- Emergency Stop button (🛑) clears all selections

## Other Session Types
## RDP Session Controls

When connected to an RDP session:

| Button | Action | Shortcut |
|--------|--------|----------|
| Connect/Disconnect | Start or stop RDP session | — |
| Ctrl+Alt+Del | Send Ctrl+Alt+Del to remote | — |
| Fullscreen | Toggle fullscreen mode | F11 |
| — | Exit fullscreen | Esc |

### RDP Security

- **Certificate Trust On First Use (TOFU)**: First connection to a new server shows a certificate dialog. Verify the SHA-256 fingerprint before trusting. Trusted fingerprints are stored in `~/.config/openadmindesk/rdp_known_certs.json`.
- **NLA Authentication**: Enabled by default. Uses vault credentials — never passed as command-line arguments.
- **Gateway**: TS Gateway credentials stored in vault, referenced by `rdp_gateway_credential_id`.
- **VNC**: scaling, view-only, color depth
- **Telnet**: plaintext warning before connecting (legacy compatibility)
- **Local Shell**: opens local terminal in a tab

## Settings
- File → Settings (or ⚙ button)
- Terminal tab: font, size, background opacity, scrollback lines
- SFTP tab: show hidden files, default path, double-click action
- Logging tab: log level
