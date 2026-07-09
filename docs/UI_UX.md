# UI and UX Direction

## Main Layout

OpenAdminDesk starts directly in the working interface:

- top toolbar for quick connect and common actions,
- left connection tree,
- central tabbed workspace,
- optional bottom status/event area,
- right or bottom detail panels only when useful.

Do not build a marketing landing page inside the app.

## Connection Tree

The tree should support:

- folders,
- saved SSH profiles,
- search/filter,
- protocol/status icons,
- context menu actions,
- keyboard navigation.

The tree should remain readable with hundreds of connections.

## Tabs

Tabs should show:

- profile name,
- connection status,
- activity indicator later,
- close action.

Future split panes must be possible without rewriting the workspace model.

## Scaling

- Use Qt layout managers, not absolute positioning.
- Avoid fixed text sizes except for terminal font configuration.
- Respect Qt high-DPI scaling.
- Test at 1366x768, 1920x1080, and HiDPI scaling.

## Visual Style

The UI should feel modern, calm, and professional:

- clear hierarchy,
- restrained colors,
- readable spacing,
- strong focus states,
- consistent icons,
- no copied proprietary trade dress.

## First Screens

The first usable screens are:

1. Main shell with connection tree and empty tab workspace.
2. New SSH profile dialog.
3. Credential unlock/setup dialog.
4. SSH terminal tab.
5. SFTP browser tab or side panel.

