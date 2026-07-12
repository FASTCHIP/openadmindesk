# Feature Matrix

Use this table to track product coverage. Agents should update it when a
feature moves from planned to implemented or tested.

| Feature | MVP | Implemented | Tested | Notes |
| --- | --- | --- | --- | --- |
| Main window shell | yes | yes | yes | QSplitter: tree + tabs + status area |
| Activity rail / compact workbench shell | yes | yes | yes | Left activity rail with Sessions/SFTP/Tunnels/Tools/Macros/Vault modes, compact session tree, and split workspace controls |
| Session Wizard 2.0 protocol grid | partial | yes | yes | Compact protocol cards for SSH/RDP/Telnet/VNC/Local Shell, disabled roadmap cards for SFTP/FTP/Serial/Browser/Mosh, templates, and launch behavior |
| SFTP path navigation | partial | yes | yes | Path entry, back/forward history, root/home buttons, refresh, hidden-file toggle, and tree navigation tests |
| Broadcast / MultiExec safety | partial | yes | yes | Broadcast now refuses zero-target activation, requires confirmation, and shows connected target count |
| User-reported SSH/profile/settings regression fixes | yes | yes | yes | SSH no longer auto-discovers client keys, SSH editor hides RDP-only rows, central terminal font uses a combo box and applies to terminals, default activity rail shows only Sessions |
| Connection tree | yes | yes | yes | Profiles from ProfileStore, context menu |
| SSH profile model | yes | yes | yes | Profile dataclass, validation |
| OpenSSH argv builder | yes | yes | yes | ssh_option_mapper.py, safe args |
| Tabbed terminal workspace | yes | yes | yes | SSHTerminalBackend, async tabs |
| SFTP browser (dedicated tab) | yes | yes | yes | Dedicated file-browser tab with expandable directory tree, upload/download, and context actions |
| SFTP side browser (attached) | later | yes | yes | Side panel inside SSH terminal tab; open/close/detach actions; uses same Profile and vault credentials |
| SFTP transfer queue | later | yes | yes | TransferJob model + TransferQueue engine; queue widget with progress/status/cancel/retry; upload/download/drop routed through queue; conflict resolution dialog (overwrite/rename/skip); auto-retry on failure |
| Remote edit safety | later | yes | yes | Binary/size guard before download; remote mtime/size snapshot; conflict check on save; Overwrite/Save As/Cancel dialog; temp dir cleanup on success/cancel |
| Session Wizard advanced pages | later | yes | yes | SSH advanced: agent, compression, keepalive, X11, proxy; RDP advanced: gateway, cert, drives, printers, clipboard, multimon; VNC advanced: scaling, view-only, color depth; Summary page with security notes; tests verify persistence without plaintext credential regressions |
| MultiExec Panel (broadcast) | later | yes | yes | MultiExecPanel dock with session list, opt-in checkboxes, target count, emergency stop; per-tab banner; broadcast only sends to opted-in connected tabs; no-target rejection; tests for selection, count, stop, and disconnect auto-clear |
| Central settings dialog | later | yes | yes | Versioned AppSettings model + JSON SettingsStore; QTabbed dialog (General/Terminal/SFTP/Logging); SFTP settings applied in browser (hidden files, tree font, double-click action, default path); migration tests for v0→v1; graceful missing/corrupt file handling |
| Session Manager power features | later | yes | yes | Favorite/tags/last-connected/error/duration in Profile model & SQL store; search by tags & protocol prefix; folder launch (open all); context actions: export single profile, Copy SSH command, Open SFTP, desktop shortcut placeholder; ★ indicator in tree; metadata in tooltip |
| SSH/SFTP host-key trust | yes | yes | yes | Explicit TOFU policy with pending fingerprint and user-approved OpenAdminDesk `known_hosts` store |
| RDP gateway credentials | later | yes | yes | `rdp_gateway_credential_id` links TS Gateway auth to a separate vault account; plaintext gateway password is not stored in profiles |
| Credential vault | yes | yes | yes | PBKDF2 + AES-256-GCM, master password |
| Account manager UI | yes | yes | yes | Add/edit/remove, vault menu integration |
| Local forwards | yes | yes | yes | SSH `-L`, TunnelManagerWidget |
| Remote forwards | yes | yes | yes | SSH `-R` |
| Dynamic SOCKS forwards | yes | yes | yes | SSH `-D` |
| X11 forwarding | yes | yes | yes | SSH `-X`/`-Y`, X11Detector |
| Remote GUI launcher | yes | yes | yes | GuiLauncher with X11 |
| Snippets | later | yes | yes | SnippetStore, dropdown in SSH tab |
| Import/export | yes | yes | yes | JSON/CSV via ProfileImporter/Exporter |
| AppImage packaging | yes | yes | yes | Built with AppImageKit appimagetool; `--version` smoke passed |
| Debian package | later | yes | yes | `.deb` built; extracted console script `--version` smoke passed |
| RPM package | later | yes | yes | `.rpm` built; extracted console script `--version` smoke passed |
| Linux desktop integration | later | yes | yes | Shared `.desktop` and SVG assets; deb/rpm/AppImage package smoke checks verify installed metadata |
| MobaXterm-class UX gap plan | later | planned | no | `docs/MOBAXTERM_GAP_PLAN.md` defines phased workbench, SFTP, terminal, sessions, tools, settings, and release-quality upgrades |
