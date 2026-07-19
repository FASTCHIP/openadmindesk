# MobaXterm Reference Gap Plan

This document compares OpenAdminDesk with the public MobaXterm documentation and screenshots, then turns the gaps into an implementation plan. The goal is not to clone branding, proprietary assets, or exact UI artwork. The goal is to approach the same quality bar for administrator workflows using open-source, cross-platform components.

## Reference Sources

- MobaXterm features page: https://mobaxterm.mobatek.net/features.html
- MobaXterm documentation: https://mobaxterm.mobatek.net/documentation.html
- Main terminal/session screenshot: https://mobaxterm.mobatek.net/img/moba/features/feature-terminal.png
- Session type chooser screenshot: https://mobaxterm.mobatek.net/img/moba/features/feature-sessions.png
- Graphical SFTP browser screenshot: https://mobaxterm.mobatek.net/img/moba/features/feature-sftp-browser.png

## Reference UX Summary

MobaXterm positions itself as a single remote-computing toolbox: terminal, saved sessions, SFTP/FTP, RDP/VNC/XDMCP, X11, tunnels, macros, password management, local Unix-like tools, network tools, settings, and plugins in one compact desktop shell.

Key observable patterns:

- A persistent left sidebar holds quick connect, session folders, tools, macros, and protocol-specific side panels.
- SSH sessions open as terminal tabs and automatically expose a graphical SFTP browser in the left sidebar.
- The session wizard is protocol-first and visually compact: SSH, Telnet, Rsh, XDMCP, RDP, VNC, FTP, SFTP, Serial, File, Shell, Browser, Mosh.
- The top menu/toolbar exposes Sessions, View, X server, Tools, Settings, Macros, Help, split modes, tunnels, services, and settings.
- Multi-tab, split terminal, detach tab, and multi-execution workflows are first-class.
- Remote file editing is direct: double-click a remote file, edit locally, and save back through SFTP/SCP.
- Global settings cover terminal behavior, fonts, charset, paste behavior, logging, keyboard shortcuts, X11, display, and storage.
- The product feels compact and operations-focused rather than wizard-heavy.

## Current OpenAdminDesk Position

OpenAdminDesk already has a meaningful foundation:

- Main window, connection tree, quick connect, tabbed workspace.
- SSH terminal via Paramiko/pyte with Qt worker boundaries.
- SFTP browser with upload/download/context actions and recent repair for directory type preservation.
- Vault, account manager, TOFU host-key policy, profile store, import/export.
- RDP/VNC/Telnet/local shell prototypes.
- Tunnels, snippets, remote GUI launcher, X11 detection.
- AppImage/deb/rpm packaging and tests.

Main gap: the features are present as modules, but the UX is not yet a cohesive MobaXterm-class workbench. The next work should focus on workflow integration, visual density, session ergonomics, and production-grade protocol behavior.

## Gap Matrix

| Area | MobaXterm Reference | OpenAdminDesk Now | Gap | Priority |
| --- | --- | --- | --- | --- |
| Main shell | Compact menu + left sidebar + tabs + tool sidebars | Main window with connection tree and tabs | Needs unified sidebar modes and denser toolbar | P0 |
| Session chooser | Icon grid for many protocols | SessionWizard supports core types | Needs protocol grid, presets, advanced per-protocol pages | P0 |
| SFTP with SSH | Auto sidebar browser during SSH session | Dedicated SFTP tab after recent repair | Needs optional attached sidebar mode, follow-terminal-folder, better transfer queue | P0 |
| Terminal quality | Mature PuTTY-like terminal, split, detach, multiexec | pyte renderer, tabs, broadcast | Needs split layouts, detach polish, terminal compatibility tests | P0 |
| Session manager | Saved sessions in sidebar, folders, right-click operations, shortcuts | ConnectionTree folders/search/context | Needs launch groups, favorites, recent, desktop shortcuts, richer metadata | P1 |
| Tunnels | Graphical SSH tunnel manager | TunnelManagerWidget exists | Needs persistent tunnel dashboard and live status | P1 |
| X11/remote GUI | Integrated X server and remote GUI workflows | X11 detector + launcher | Needs X server strategy per platform and clearer GUI launch workflow | P1 |
| Remote desktops | RDP/VNC/XDMCP settings | RDP/VNC prototypes | Needs deep options, diagnostics, credential flows, XDMCP decision | P1 |
| File editing | Double-click remote file, edit, save back | SFTP edit prototype | Needs editor integration, diff, conflict detection, binary guard | P1 |
| Tools | Network tools, editors, package/plugins, services | Some managers/prototypes | Needs tools hub and plugin/extension model | P2 |
| Settings | Broad global settings | Scattered settings/dialogs | Needs centralized settings with persistence | P1 |
| Portability/package polish | Portable single app feel | Linux packages available | Needs portable profile, config import/export, upgrade path | P2 |
| Documentation/evidence | Mature docs/screenshots | Dev docs + smoke templates | Needs user manual and visual smoke evidence | P2 |

## Implementation Plan

### Phase 1 - Workbench UX Shell (P0)

Goal: make the first screen feel like a remote-admin workbench, not a collection of prototypes.

Tasks:

- Add a left activity rail with modes: Sessions, SFTP, Tunnels, Tools, Macros, Vault.
- Keep the session tree visible by default and make it denser: compact rows, protocol icons, favorites, recent sessions.
- Add a top toolbar/menu layout inspired by the reference categories: Session, View, Tools, Tunnels, Settings, Help.
- Add explicit split controls to the workspace: single, 2-horizontal, 2-vertical, 4-grid.
- Add tab detach/reattach/fullscreen polish and visible context menu commands.
- Add tests for tab layout state, sidebar mode switching, and persistence.

Acceptance:

- A new user can discover quick connect, saved sessions, SFTP, tunnels, vault, settings, and tools without opening menus randomly.
- The UI remains compact at 1200x800 and usable at laptop sizes.

### Phase 2 - Session Wizard 2.0 (P0)

Goal: match the protocol-first session creation ergonomics.

Tasks:

- Replace the current wizard first page with a compact icon grid: SSH, Telnet, RDP, VNC, SFTP, FTP placeholder, Serial placeholder, Local Shell, Browser placeholder, Mosh placeholder.
- Add per-protocol advanced sections without overwhelming the basic page.
- Add profile templates: Linux SSH, Windows RDP, Jump-host SSH, SFTP-only, VNC, Local shell.
- Add launch behavior: save only, save and connect, temporary connect.
- Add validation previews: final connection string summary and security notes.

Acceptance:

- Creating a common SSH/SFTP/RDP/VNC session takes no more than one basic page plus Finish.
- Unsupported protocols are visible as planned/disabled, not silently absent.

### Phase 3 - SFTP Experience Upgrade (P0)

Goal: make SFTP feel like the reference graphical SSH browser.

Tasks:

- Support two modes: dedicated SFTP tab and attached side browser next to an SSH terminal.
- Add a “Follow terminal folder” option. Detect shell `pwd` heuristically or use explicit command injection with user consent.
- Add transfer queue panel with progress, cancel, retry, overwrite/rename decisions.
- Add breadcrumbs/path entry, back/forward history, home/root buttons, refresh, hidden-file toggle.
- Add drag/drop both directions where the platform permits it.
- Make double-click behavior configurable: open, download, edit, or preview.
- Add remote edit conflict handling: compare mtime/size before upload, warn on remote changes.
- Add tests around directory navigation, transfer queue state, edit roundtrip, and attached/dedicated mode.

Acceptance:

- SFTP is usable without terminal knowledge: browse, upload, download, edit, delete, chmod, mkdir, refresh.
- It never writes file-browser status into terminal output.

### Phase 4 - Terminal Fidelity And Multi-Execution (P0)

Goal: close the biggest quality risk against a mature terminal emulator.

Tasks:

- Build a terminal compatibility test suite: alternate screen, resize, bracketed paste, mouse reporting, truecolor, scrollback, selection, copy/paste, cursor modes.
- Add command broadcast safety: clear banner, target count, per-tab opt-in, emergency stop.
- Implement MultiExec view: visible selected terminals receiving the same input.
- Add paste protection: warn before multi-line paste, configurable paste delay.
- Add terminal logging per profile/global settings.
- Decide whether pyte remains good enough after tests or whether VTE/terminal-widget backend is needed on Linux.

Acceptance:

- Common TUIs (`vim`, `top`, `mc`, `htop`, `less`) are manually smoke-tested and tracked.
- MultiExec cannot accidentally broadcast without visible state.

### Phase 5 - Session Manager Power Features (P1)

Goal: make saved sessions as useful as MobaXterm’s sidebar.

Tasks:

- Add favorites, recently used, tags, search by host/user/notes/protocol.
- Add launch folder/group: open all sessions in a folder.
- Add per-session context actions: connect, SFTP, edit, duplicate, export, create desktop shortcut, copy SSH command, open containing folder.
- Add import quality pass for MobaXterm/PuTTY including folder hierarchy and unsupported field reporting.
- Add session health metadata: last connected, last error, last duration.

Acceptance:

- An admin with 100+ sessions can find, group, and launch sessions quickly.

### Phase 6 - Tunnels, Gateways, And Network Tools (P1)

Goal: raise tunnels/tools from prototype to operational dashboard.

Tasks:

- [x] Add tunnel dashboard with running/stopped/error states, local port checks, logs, restart, autostart.
- [x] Add SSH gateway model shared by SSH/Telnet/RDP/VNC/SFTP profiles.
- [x] Add network tools hub: ping, traceroute, DNS lookup, port scan, whois, HTTP check, key/fingerprint viewer.
- [x] Add safe command execution wrappers and output panes.

Acceptance:

- A user can create, start, diagnose, and stop tunnels without reading logs manually.

### Phase 7 - Remote Desktop And X11 Maturity (P1)

Goal: make RDP/VNC/X11 workflows predictable.

Tasks:

- Expand RDP options: admin console, clipboard, drives, printers, smartcard, graphics, keyboard shortcuts, cert policy, gateway credential selector.
- Expand VNC options: encoding, color depth, view-only, scaling, password/vault integration.
- Decide XDMCP support explicitly: implement through available open-source clients or mark unsupported with rationale.
- Improve X11 workflow: display status, trusted/untrusted forwarding, remote app launcher presets, diagnostics.

Acceptance:

- RDP/VNC failure diagnostics show actionable client stderr/status.
- X11 launch flow explains local dependency status and remote DISPLAY behavior.

### Phase 8 - Settings And Persistence (P1)

Goal: centralize behavior into a serious settings surface.

Tasks:

- Add global settings dialog with sections: General, Terminal, Sessions, SFTP, X11, RDP/VNC, Vault, Sync, Shortcuts, Appearance.
- Persist settings in a versioned config file with migration tests.
- Add keyboard shortcut editor and command palette.
- Add profile-level overrides for terminal theme, SFTP behavior, logging, and paste policy.

Acceptance:

- Settings survive restart and are test-covered through migration fixtures.

### Phase 9 - Tools/Extensions Hub (P2)

Goal: approximate the toolbox/plugin advantage without bundling proprietary pieces.

Tasks:

- Create a Tools hub panel with built-in utilities and extension entry points.
- Add local tool discovery for installed open-source binaries: ssh, sftp, rsync, xfreerdp, remmina, vncviewer, nmap, tcpdump, iperf, dig.
- Add extension manifest format for registering tools and panels.
- Add update-safe plugin loading rules and security model.

Acceptance:

- New tools can be added without editing the main window directly.

### Phase 10 - Evidence, Polish, And Release Quality (P2)

Goal: make quality visible and repeatable.

Tasks:

- Fill `docs/GUI_SMOKE_EVIDENCE.md` with real SSH/SFTP/RDP/VNC/Local Shell evidence.
- Add screenshot-based visual smoke tests for main shell, session wizard, SSH tab, SFTP browser, tunnels, settings.
- Add a user manual with screenshots and common workflows.
- Add release checklist: package build, install, first run, import, vault unlock, connect, SFTP, RDP/VNC, uninstall.
- Add crash/log collection and redaction rules.

Acceptance:

- A release candidate has package artifacts plus documented manual evidence.

## Immediate Next Sprint

Start with these tasks because they most directly affect perceived quality:

1. Build activity rail and compact session/sidebar layout.
2. Add dedicated SFTP attached-sidebar mode with transfer queue and path history.
3. Replace Session Wizard protocol selection with icon grid and protocol templates.
4. Add split workspace controls and MultiExec safety UI.
5. Add global Settings skeleton with Terminal and SFTP sections.

## Non-Goals / Guardrails

- Do not copy MobaXterm branding, icons, screenshots, or proprietary behavior verbatim.
- Prefer existing open-source components where terminal/RDP/VNC/X11 fidelity is hard.
- Keep secrets out of argv, SQLite profile rows, exported profiles, logs, and screenshots.
- Keep tests tied to behavior, not only widget existence.
- Every user-visible workflow should have either automated tests or manual smoke evidence.
