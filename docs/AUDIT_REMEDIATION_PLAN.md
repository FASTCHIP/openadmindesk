# OpenAdminDesk Audit Remediation Plan

Date: 2026-07-11
Status: active source of truth for stabilization work

## Summary

The project has grown into a useful prototype, but it is not yet stable enough
for feature expansion. The main risks are repository hygiene, broken lint/test
baseline, plaintext secret storage, unsafe Qt threading, and an unresolved
terminal/SSH architecture split between documentation and code.

Use this file instead of older audit or improvement reports.

## Evidence Snapshot

Initial audit observations on `/ai/openadmindesk`:

- `git ls-files` tracks mostly documentation and empty package files; most real
  code, tests, CI, Dockerfile, and lockfile are untracked.
- Runtime files exist in the project tree: `profiles.db`, `data/profiles.db`,
  `sync_config.json`.
- Baseline finding: `pytest -q` aborted with `Fatal Python error: Aborted` in `tests/test_app.py`
  because the test calls the real Qt `main()`/event loop.
- Baseline finding: `ruff check .` reported 120 errors, including real runtime failures such as
  undefined Qt classes and `_()` shadowing by file-dialog variables.
- Baseline finding: `ProfileStore` stored `password`, `private_key_passphrase`, and
  `rdp_gateway_password` in SQLite profile rows. New saves now store
  `credential_id` and leave those secret columns empty; explicit legacy migration
  is available through `tools/migrate_profile_secrets.py`.
- Vault KDF is now documented honestly as PBKDF2-HMAC-SHA256 with 100k
  iterations; Argon2id remains a future hardening option.
- Baseline finding: SSH/SFTP host-key handling was warning-only; Paramiko
  backends now load system host keys and reject unknown hosts by default.
- Baseline finding: RDP passed passwords through command-line arguments and used
  `/cert:ignore`; Linux RDP command construction now omits password arguments and
  uses `/cert:tofu`.
- SSH connect used to block the GUI thread, and backend output could call Qt
  widgets from worker threads. SSH, local shell, and SFTP connect/list now use
  worker/signal boundaries.
- Baseline finding: docs described OpenSSH/VTE-first architecture while current
  code used Paramiko plus a custom `pyte` renderer. Decision record now
  stabilizes on Paramiko/pyte-first for this prototype.

## Rules For This Plan

- Complete phases in order unless the user explicitly reprioritizes.
- Each task should be small enough for a weak model to finish safely.
- Every task must update `docs/WORKLOG.md`.
- Do not mark a task done without a verification command or recorded blocker.
- Do not add new product features until Phases 0-3 are complete.

## Phase 0 - Repository Hygiene

Goal: make the real working project versioned and keep local state/secrets out of git.

- [x] Update `.gitignore` to ignore runtime state: `profiles.db`, `data/*.db`,
  `vault.json`, `sync_config.json`, logs, local sync files, and generated caches.
- [x] Decide which untracked source/test/tool/docs files are real project files.
- [x] Stage real source, tests, CI, Dockerfile, lockfile, and maintained docs.
- [x] Remove or archive local runtime databases from the project tree.
- [x] Verify with `git status --short` that no runtime secrets or local databases
  are visible as untracked files.

Verification:

```bash
git status --short
find . -maxdepth 3 \( -name 'profiles.db' -o -name 'vault.json' -o -name 'sync_config.json' \) -print
```

## Phase 1 - Lint And Runtime Import Baseline

Goal: remove failures that make code paths crash before behavior can be tested.

- [x] Fix `F821` undefined names in UI modules, starting with
  `ui/session_wizard.py` and `ui/sftp_file_browser.py`.
- [x] Fix `F823` `_` shadowing caused by file-dialog assignments like `path, _ = ...`.
- [x] Fix `F811` redefinitions in `ui/main_window.py` and similar modules.
- [x] Fix `tools/build.py` RPM f-string macro escaping.
- [x] Remove unused imports only after runtime errors are fixed.
- [x] Reach a clean `ruff check src tools` baseline.
- [x] Then reach a clean `ruff check tests` baseline.

Verification:

```bash
ruff check src tools
ruff check tests
```

## Phase 2 - Test Harness Baseline

Goal: make tests reliable and headless-safe.

- [x] Refactor `openadmindesk.app.main()` tests so they do not call the real
  `app.exec()` event loop.
- [x] Add or configure a headless Qt test setup (`QT_QPA_PLATFORM=offscreen` or
  pytest-qt) for UI tests.
- [x] Split tests into core tests and Qt UI tests so core can run without a display.
- [x] Replace superficial `hasattr` tests with behavior checks when touching a module.
- [x] Reach a non-aborting `pytest -q` run, even if some assertions still fail.
- [x] Then drive failing assertions down one file at a time.

Verification:

```bash
pytest -q -m 'not qt'
pytest -q
```

## Phase 3 - Secret Storage And Vault Model

Goal: stop storing credentials in plaintext profile metadata.

- [x] Add a credential reference field to profiles, for example `credential_id`.
- [x] Stop writing `password`, `private_key_passphrase`, and
  `rdp_gateway_password` into `profiles` rows for new saves.
- [x] Add a migration that moves existing profile secrets into the vault or clears
  them with explicit user confirmation.
- [x] Update profile editor/session wizard to store credentials through the vault.
- [x] Make profile import/export omit secrets by default.
- [x] Add tests proving plaintext secrets are not saved to SQLite or exported JSON.
- [x] Decide vault KDF: implement Argon2id or update docs to PBKDF2 honestly.
- [x] Add vault versioning, atomic writes, and restrictive file permissions.
- [x] Add vault auto-lock timeout or a documented follow-up.

Verification:

```bash
pytest tests/test_profile_store.py tests/test_vault_manager.py tests/test_profile_import_export.py tests/test_profile_secret_migration.py tests/test_session_wizard.py tests/test_profile_editor.py -q
```

## Phase 4 - Qt Threading And Session Lifecycle

Goal: prevent UI freezes and cross-thread widget access.

- [x] Move SSH connect/disconnect/read lifecycle into a worker object or thread.
- [x] Emit Qt signals for output, status, and errors; update widgets only in main thread.
- [x] Apply the same boundary to SFTP operations and local shell output.
- [x] Add cancellation semantics that actually stop pending connection attempts.
- [x] Ensure reconnect and close paths join/stop worker resources safely.
- [x] Add tests or manual smoke notes for connect failure, cancel, reconnect, and close.

Verification:

```bash
pytest tests/test_ssh_terminal_tab.py tests/test_local_shell_tab.py tests/test_sftp_file_browser.py tests/test_sftp_backend.py -q
```

## Phase 5 - Terminal And SSH Architecture Decision

Goal: stop mixing incompatible architecture directions.

- [x] Write a decision record in `docs/DECISIONS.md`: OpenSSH/VTE-first vs
  Paramiko/pyte-first, with tradeoffs.
- [x] OpenSSH/VTE adapter is not applicable for the current decision;
  `docs/DECISIONS.md` records Paramiko/pyte-first for this prototype.
- [x] If Paramiko/pyte-first is kept, document unsupported terminal features and
  add compatibility tests for escape sequences, resizing, paste, mouse, and
  alternate screen.
- [x] Make `TerminalBackend` signatures match real implementations.
- [x] Remove dead or unused backend interfaces after the chosen contract is in use.

Verification:

```bash
python3 -m py_compile src/openadmindesk/core/terminal_backend.py src/openadmindesk/core/ssh_terminal_backend.py
pytest tests/test_terminal_backend.py tests/test_terminal_widget.py -q
```

## Phase 6 - Protocol Security And Diagnostics

Goal: make protocol launches safer and debuggable.

- [x] Replace SSH/SFTP warning-only unknown host-key handling with reject or
  explicit user-confirm-and-save flow.
- [x] Stop passing RDP passwords through process arguments.
- [x] Replace `/cert:ignore` with an explicit certificate policy and warning.
- [x] Capture useful stderr/status for RDP/VNC/tunnel launches instead of sending
  everything to `/dev/null`.
- [x] Validate proxy/jump host fields and document supported formats.
- [x] Add tests for unsafe inputs and command argument construction.

Verification:

```bash
pytest tests/test_rdp_backend.py tests/test_sftp_backend.py tests/test_tunnel_manager.py -q
```

## Phase 7 - Product Workflow Consistency

Goal: make visible features work end-to-end before adding more.

- [x] Session Wizard supports every `SessionType` that MainWindow can open.
- [x] Folder selected in Session Wizard is saved to the profile.
- [x] SFTP browser reuses or intentionally separates SSH session state; document the decision.
- [x] Import/export, sync, duplicate, and delete flows do not leak credentials.
- [x] Create a manual smoke checklist for: create profile, connect SSH, resize,
  SFTP browse, reconnect, close, import/export, vault lock/unlock.

Verification:

```bash
pytest tests/test_session_wizard.py tests/test_profile_editor.py tests/test_connection_tree.py -q
```

If a listed test file does not exist yet, create the smallest useful one as part
of the task.

## Phase 8 - Packaging And Release

Goal: package only after the app has a reliable baseline.

- [x] Ensure Dockerfile matches Python version and app entrypoint.
- [x] Add a real `--version` or remove Docker test that expects it.
- [x] Fix AppImage/deb/rpm build scripts in a clean environment. Verified on the
  server after installing Debian/RPM build dependencies, FUSE2 compatibility,
  and `appimagetool`.
- [x] Smoke test installed package launch.
- [x] Document supported Linux distributions and required system tools.

Verification:

```bash
python tools/build.py check
python tools/build.py python-pkg
python tools/build.py appimage
python tools/build.py rpm
python tools/build.py deb
```

## Do Not Do Yet

- Do not add FTP, Serial, WSL, split panes, bookmarks, or macro improvements
  until Phases 0-3 are done.
- Do not polish themes before terminal architecture is decided.
- Do not claim MobaXterm parity. Track concrete workflows instead.
- Do not mark packaging complete based only on scripts existing.

## Phase 9 - Post-publication Security Hardening

Goal: Implement additional security measures after the initial publication.

- [x] 9.1 ProfileStore rejects new unprotected primary/gateway secrets; credential IDs persist NULL; legacy readable (commits through a8d39c6).
- [x] 9.2 VaultManager atomic non-mutating account upsert/rollback (ebc4f6b+393d430).
- [x] 9.3 ProfileEditor requires unlocked vault for entered secrets, upsert/no remove, failure UX, tests (60e8e38 through cbcc3e3/632ca6a).
- [x] 9.4 SessionWizard saved modes require unlocked vault + successful vault/store writes; temporary-connect remains memory-only; tests. (refs ddd6ace+4804fcb+848e64c)
- [ ] 9.5 ProfileEditor and SessionWizard credential UI vault-before-store orphan transaction ordering. (refs ddd6ace+4804fcb+848e64c) - vault write succeeds then store failure can orphan account, so 9.5 remains active
- [ ] 9.6 Legacy plaintext migration dry-run/backup/report/schema plan.
- [ ] 9.7 SSH ProxyCommand connect-time revalidation/tests.
- [ ] 9.8 Passive periodic vault auto-lock UI timer/tests.
- [ ] 9.9 Versioned vault KDF migration/Argon2id design+tests.
- [ ] 9.10 Telnet cleartext warning; tunnel logging; executor lifecycle as separate sub-bullets.
- [ ] 9.11 Packaging/release clean-env verification and demo E402 hygiene.

Verification:

```bash
pytest tests/test_profile_store.py tests/test_vault_manager.py tests/test_profile_editor.py tests/test_session_wizard.py -q
```
