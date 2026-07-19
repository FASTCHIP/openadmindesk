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

## Evidence Table

### SSH Terminal

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | SSH connect + commands | Linux server (22) | 1. Create SSH profile via wizard. 2. Connect, trust host key. 3. Run `whoami && hostname`. 4. Resize terminal. 5. Run `ls -la /`. 6. Disconnect. 7. Reconnect. | Terminal renders output; resize works; reconnect succeeds; no secrets in logs | pending | pending |
| pending | SSH auth failure | Invalid credentials | 1. Open SSH profile with wrong password. 2. Observe error. | Error message shown in status area; terminal does not open | pending | pending |

### SFTP Browser

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | SFTP browse + upload | SSH server (22) | 1. Connect via SSH. 2. Open SFTP sidebar (📁). 3. Navigate directories. 4. Upload a small text file. 5. Download it to /tmp. 6. Delete remote file. 7. Toggle hidden files. | Files list correctly; upload/download complete; delete works; no crash | pending | pending |
| pending | SFTP transfer queue | SSH server | 1. Open SFTP. 2. Queue 3 uploads and 2 downloads. 3. Cancel one transfer. 4. Retry failed transfer. | Queue shows progress; cancel stops transfer; retry reattempts | pending | pending |

### RDP Session

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | RDP TOFU + connect | Windows VM (3389) | 1. Create RDP profile with NLA enabled. 2. Connect — verify certificate dialog appears. 3. Trust certificate. 4. Verify remote desktop renders. 5. Click Ctrl+Alt+Del button. 6. Toggle fullscreen (F11 or button). 7. Disconnect. | TOFU dialog shows fingerprint; remote desktop visible; CAD sent; fullscreen works | pending | pending |
| pending | RDP wrong cert | Self-signed cert VM | 1. Create profile with known cert. 2. Connect, trust cert. 3. Change server cert. 4. Reconnect. 5. Verify warning/TOFU prompt appears. | TOFU dialog appears for changed certificate; trusted cert auto-accepted | pending | pending |
| pending | RDP diagnostics | Offline host | 1. Create RDP profile with unreachable host. 2. Connect. 3. Observe error. | Error in status area; no subprocess crash; no secrets in diagnostics | pending | pending |

### VNC Session

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | VNC connect | VNC server (5900) | 1. Create VNC profile. 2. Connect. 3. Verify remote desktop renders or clear error appears. 4. Disconnect. | Client launches with rendering or diagnostics shown | pending | pending |

### Local Shell

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | Local Shell basic | local workstation | 1. Create Local Shell profile. 2. Open — shell appears in tab. 3. Run `echo test && pwd`. 4. Close tab, reopen. | Shell output appears; close/reopen clean; no crash | pending | pending |

### Import/Export Security

| Date | Workflow | Target | Steps | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| pending | Export check | Any profile | 1. Create profile with vault-linked credentials. 2. Export as JSON. 3. Open JSON, verify no password/private_key_passphrase/rdp_gateway_password fields present. | Exported JSON contains no plaintext secrets | pending | pending |

## Execution Notes

- Use disposable credentials and temporary paths for all tests.
- Take screenshots of: (1) connected session, (2) error/diagnostics display, (3) TOFU/certificate dialog.
- After each run: verify `~/.local/share/openadmindesk/profiles.db` has NULL password columns for vault-linked profiles.
- Confirm exported profile JSON contains no `password`, `private_key_passphrase`, or `rdp_gateway_password` keys.
- Keep screenshots and logs free of secrets before committing or sharing.
- Test on at least: Ubuntu 22.04 or 24.04 desktop, with Python 3.12+.

## Completion Criteria

All evidence rows must have a date, actual result, and evidence reference before marking the roadmap item complete.
