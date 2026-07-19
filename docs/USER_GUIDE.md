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
- **RDP**
  - **Built-in Client**: RDP sessions render inside the application window using the embedded FreeRDP client — no external RDP application required.
  - **Network Level Authentication (NLA)**: Enabled by default. Enter a Windows domain in the session wizard or profile editor if needed.
  - **Certificate Trust On First Use (TOFU)**: On first connection, verify the server's SSL certificate fingerprint in the dialog before trusting. Trusted fingerprints are stored in `~/.config/openadmindesk/rdp_known_certs.json`.
  - **Controls**: Fullscreen toggle (F11 or toolbar button), Ctrl+Alt+Del injection, clipboard sync between local and remote sessions.
  - **Advanced Options**: Configure TS Gateway, certificate policy (auto/warn/ignore), drive redirection, printer redirection, clipboard redirection, and multi-monitor support in the Session Wizard or Profile Editor.
- **VNC**: scaling, view-only, color depth
- **Telnet**: plaintext warning before connecting (legacy compatibility)
- **Local Shell**: opens local terminal in a tab

## Settings
- File → Settings (or ⚙ button)
- Terminal tab: font, size, background opacity, scrollback lines
- SFTP tab: show hidden files, default path, double-click action
- Logging tab: log level
