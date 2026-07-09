# Worklog

Use this file as the chronological project journal. New entries go at the top.

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
