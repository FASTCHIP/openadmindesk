# Worklog

Use this file as the chronological project journal. New entries go at the top.

## 2026-07-09

Plan:

- Add the second layer of project guidance needed for reliable agent
  implementation.
- Define data models, SSH option mapping, UI structure, vault behavior,
  development setup, tests, and acceptance criteria.

Changes:

- Added implementation rules, feature matrix, UI spec, data model, SSH option
  mapping, vault spec, development environment, test plan, and acceptance
  criteria.
- Linked these documents from README, AGENTS, agent context, and roadmap.

Verification:

- Pending: sync these documents to `/ai/openadmindesk` and run the smoke check.

## 2026-07-09

Plan:

- Create a clean `/ai/openadmindesk` project workspace on the server.
- Preserve the user's product goal: modern MobaXterm-like convenience for
  Linux, without copying proprietary assets or implementation.
- Define docs that a simple LLM agent can follow.

Changes:

- Updated local project scaffold for OpenAdminDesk.
- Defined product requirements for connection tree, tabs, SSH/SFTP, credential
  vault, tunnels, and X11 forwarding.
- Added roadmap phases that keep early tasks small for simple LLM agents.

Verification:

- Created `/ai/openadmindesk` on `10.1.150.112`.
- Transferred the scaffold to the server.
- Initialized git and renamed the initial branch to `main`.
- Verified files are owned by `fastchip:fastchip`.
- Ran smoke command: `PYTHONPATH=src python3 -m openadmindesk.app`.
- Local `python -m pytest -q` could not run because local Python does not have
  `pytest` installed.
