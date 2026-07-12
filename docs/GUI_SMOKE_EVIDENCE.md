# GUI Smoke Evidence

This file records manual GUI smoke runs against real targets. Do not mark the related roadmap item complete until every required workflow below has dated evidence, target identity, observed result, and any screenshots/log snippets the operator can safely keep.

## Current Status

Status: blocked on real target inventory and an interactive desktop session.

Required targets:

- SSH target with a disposable shell account.
- SFTP-capable target with a writable temporary directory.
- RDP target or test VM with known certificate behavior.
- VNC target or test VM.
- Local desktop shell session for Local Shell tab verification.

## Evidence Template

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | SSH terminal | pending | Open profile, trust host key if needed, run `whoami`, resize tab, reconnect | Terminal remains responsive; reconnect works | pending | pending |
| pending | SFTP browser | pending | Open SFTP, list directory, upload/download a small temp file, delete it | File operations complete and errors are visible | pending | pending |
| pending | RDP | pending | Open RDP profile with/without gateway account as applicable | Client launches without leaking secrets in argv; diagnostics visible on failure | pending | pending |
| pending | VNC | pending | Open VNC profile and connect/disconnect | Client launches or reports actionable diagnostics | pending | pending |
| pending | Local Shell | local workstation | Open Local Shell, run basic command, reconnect/close tab | Shell output appears; close/reconnect is clean | pending | pending |

## Notes

- Use disposable credentials and temporary paths.
- Confirm exported profiles do not contain passwords or gateway passwords after the run.
- Keep screenshots/logs free of secrets before committing them.
