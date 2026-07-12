# OpenAdminDesk MobaXterm-Class Next Steps

Date: 2026-07-11
Status: active product-quality follow-up after Phase 1 shell, Session Wizard grid, SFTP navigation, and Broadcast safety slices.

## Scope And Guardrails

This plan compares OpenAdminDesk against public MobaXterm documentation/screenshots already listed in `docs/MOBAXTERM_GAP_PLAN.md`. The goal is workflow quality and administrator ergonomics, not copying proprietary branding, artwork, exact layout, text, icons, or trade dress.

## Current Audit Snapshot

Recently improved and verified:

- Workbench shell: left activity rail, compact session tree, and workspace split controls exist and are tested.
- Session creation: protocol-first card grid exists for SSH, RDP, Telnet, VNC, and Local Shell; SFTP/FTP/Serial/Browser/Mosh are visible as disabled roadmap cards; templates and launch behavior exist.
- SFTP browser: dedicated tab, expandable tree, path entry, back/forward history, root/home buttons, refresh, hidden-file toggle, upload/download/edit/context actions exist.
- Broadcast/MultiExec safety: zero-target activation is rejected; enabled state requires confirmation and displays target count.
- Baseline quality: `ruff check src tools tests` and full pytest passed after the latest changes.

Remaining major gaps against the reference-quality target:

- SFTP is still a dedicated tab only. The reference workflow exposes SFTP as a side browser attached to an SSH terminal session.
- SFTP transfers are still immediate operations with progress dialogs, not a persistent transfer queue with retry/cancel/history.
- Remote edit lacks robust conflict checks against remote mtime/size before upload.
- Session Wizard templates are basic; advanced per-protocol pages are not yet available.
- Workspace split buttons currently express layout state, but they do not yet create true multi-pane terminal arrangements.
- Broadcast is safer, but there is no full MultiExec panel with visible selected targets and per-tab opt-in.
- Settings remain scattered; there is no central global settings dialog with versioned persistence.
- Session manager lacks favorites, recent sessions, tags, launch folder/group, last connected/error/duration metadata.
- Tools hub is not unified; tunnels, snippets, sync, GUI launcher, and network tools are still scattered across menus/widgets.
- Visual/manual smoke evidence is incomplete for real SSH/SFTP/RDP/VNC/local workflows.

## Next Implementation Plan

### Step 1 - True Split Workspace Panes

Goal: make split controls produce real panes, not only status/layout state.

Tasks:

- Extend `TabbedWorkspace` or add a workspace container that can host 1, 2-horizontal, 2-vertical, and 4-grid tab areas.
- Move current tabs into the active pane without losing close/currentChanged behavior.
- Add active-pane selection and open-new-session-in-active-pane behavior.
- Add tests for layout switching, tab preservation, and active-pane routing.

Acceptance:

- A user can see two or four independent tab areas on one screen.
- Existing single-pane behavior remains unchanged by default.

### Step 2 - Attached SFTP Side Browser For SSH Tabs

Goal: match the common SSH-terminal-plus-file-browser workflow.

Tasks:

- Add an optional SFTP side panel inside or next to `SshTerminalTab` using the same profile and vault-hydrated credentials.
- Keep dedicated SFTP tab mode available.
- Add a toolbar/context action: open attached SFTP, detach to tab, close attached SFTP.
- Ensure SFTP status messages go to the status area, never terminal output.
- Add tests proving attached and dedicated modes do not regress each other.

Acceptance:

- From an SSH session, a user can open a graphical file browser without creating a separate profile or leaving the terminal tab.

### Step 3 - SFTP Transfer Queue

Goal: turn file transfer from modal operations into an operational queue.

Tasks:

- Add a transfer job model: direction, local path, remote path, status, progress, error, retry count.
- Add queue widget with running/queued/done/failed states and cancel/retry controls.
- Route upload/download/drop operations through the queue.
- Add overwrite/rename/skip decisions for destination conflicts.
- Add unit tests for queue state transitions independent of live SFTP.

Acceptance:

- Long uploads/downloads remain visible and controllable after the dialog would otherwise close.

### Step 4 - Remote Edit Safety

Goal: make double-click edit trustworthy.

Tasks:

- Before uploading edited temp file, stat remote file and compare mtime/size to the originally downloaded metadata.
- Warn on remote change and offer overwrite, save as, or cancel.
- Add binary-file guard by extension/size/content sniffing.
- Clean temporary edit directories after upload/cancel where safe.
- Add tests for conflict detection logic outside the UI dialog.

Acceptance:

- Remote edit never silently overwrites a file that changed remotely during local editing.

### Step 5 - Session Wizard Advanced Pages

Goal: keep the first page simple while exposing serious per-protocol options.

Tasks:

- Add SSH advanced section: agent, key path, proxy/jump host, compression, keepalive, X11 mode.
- Add RDP advanced section: gateway, cert policy, drives, printers, multimon, clipboard.
- Add VNC advanced section: scaling, view-only, color depth, vault password.
- Add final summary/security notes page before Finish.
- Add tests that advanced fields persist to `Profile` without plaintext credential regressions.

Acceptance:

- Common profiles are still one basic page plus Finish; advanced options are available when needed.

### Step 6 - MultiExec Panel

Goal: replace implicit broadcast with visible selected-target multi-execution.

Tasks:

- Add panel listing connected SSH tabs with checkboxes and connection status.
- Require explicit per-tab opt-in before broadcast receives input.
- Add emergency stop button that disables broadcast and clears target selection.
- Add visible banner in each target tab.
- Add tests for selection, target count, stop behavior, and no-target rejection.

Acceptance:

- A user can always see exactly which terminals will receive input before typing.

### Step 7 - Central Settings Skeleton

Goal: create one place for global behavior.

Tasks:

- Add versioned settings model and storage file.
- Add settings dialog sections: General, Terminal, Sessions, SFTP, RDP/VNC, Vault, Sync, Shortcuts, Appearance.
- Start with Terminal and SFTP settings that already have behavior hooks: paste warning, hidden files default, SFTP double-click action, logging default.
- Add migration tests for settings versions.

Acceptance:

- Settings survive restart and are not scattered only in widget constructors.

### Step 8 - Session Manager Power Features

Goal: make 100+ session collections manageable.

Tasks:

- Add favorites and recent sessions to `Profile` metadata/store.
- Add last connected, last error, and last duration fields.
- Add tags and search by host/user/notes/protocol/tags.
- Add folder launch: open all sessions in folder.
- Add context actions: duplicate, export, copy SSH command, open SFTP, create desktop shortcut placeholder.

Acceptance:

- Large session collections are searchable, group-launchable, and operationally informative.

## Recommended Next Task For Agents

Start with Step 1: true split workspace panes. It is the next highest visible UX gap after activity rail and protocol grid, and it enables later MultiExec and attached SFTP layouts.

Minimum first slice:

1. Read `src/openadmindesk/ui/tabbed_workspace.py`, `src/openadmindesk/ui/main_window.py`, `tests/test_tabbed_workspace.py`, and `tests/test_main_window_layout.py`.
2. Add a small workspace container abstraction only if it keeps `MainWindow` simpler.
3. Make `single` behavior identical to today.
4. Implement `horizontal` as two tabbed panes first; leave vertical/grid as explicit follow-up only if needed.
5. Verify with targeted tests before running full `ruff` and `pytest`.
