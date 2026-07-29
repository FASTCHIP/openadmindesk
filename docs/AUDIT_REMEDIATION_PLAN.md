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
 - [x] 9.5a VaultManager atomic account removal rollback (refs atomic-rollback-9.5a)
 - [x] 9.5b ProfileEditor validate/compensate vault upsert on store failure
 - [x] 9.5c SessionWizard compensate vault upsert on store failure
 - [x] 9.6a Read-only metadata dry-run scan; fail-closed migration; real CLI tests with capsys; dead code/import cleanup. (refs Phase9.6a audit-hardening)
 - [x] 9.6b Secure SQLite+vault backup primitives (mode 0600, no plaintext JSON serialization).
 - [x] 9.6c Compensated primary+gateway migration with rollback capabilities.
 - [x] 9.6d CLI activation and schema-retirement decision.
- [x] 9.7 SSH ProxyCommand connect-time revalidation/tests.
- [x] 9.8 Passive periodic vault auto-lock UI timer/tests.
- [x] 9.9a Version-aware v1 format/KDF metadata (LEGACY_VERSION, detect_version, hex shape validation, fail-closed unlock, PBKDF metadata/timestamps, constant-time key_hash, updated_at save-rollback).
- [x] 9.9b Argon2id v2 new vaults + v1 unlock.
- [x] 9.9c Explicit v1→v2 re-encryption backup/verified rollback (core API, no UI/CLI).
- [x] 9.9d Optional UI/CLI upgrade flow. Read-only probe `inspect_vault_version()` and explicit Qt/CLI flow with `openadmindesk-vault-upgrade` tool. References to audit-hardening tasks without commit hash.
- [x] 9.10a Telnet cleartext warning; tunnel logging; executor lifecycle as separate sub-bullets.
- [x] 9.10b tunnel logging
- [x] 9.10c Executor lifecycle: idempotent close, pending-future cancellation, and predictable post-close async rejection for SFTP, ProfileStore, and VaultManager.
- [x] 9.11 Packaging/release clean-env verification and demo E402 hygiene (demo checkpoint a48f947; clean-source wheel/sdist/AppImage/deb/rpm build+extract smoke verified 2026-07-16).

Verification:

```bash
# Phase 9 verification completed in separate passes
```

## Phase 10 - Built-in RDP Client (FreeRDP ctypes)

Goal: Replace subprocess-launched system RDP clients (xfreerdp, mstsc.exe) with
a built-in RDP client that renders inside the application window and works
across all build variants (AppImage, deb, rpm, exe).

- [x] 10.1 Platform detection: add `find_freerdp_library()` to `platform_utils.py`; define FreeRDP ctypes structs and constants (`rdp_client.py`).
- [x] 10.2 Core wrapper: implement `RdpClient(QObject)` with connect/disconnect/event loop lifecycle, frame callback, Qt signals (`connected`, `disconnected`, `frame_ready`, `error_occurred`).
- [ ] 10.3 Display/frame pipeline: `RdpDisplay(QWidget)` exists, but `rdp_client.py::_on_frame_update()` remains a stub; real frame delivery/rendering is not implemented or proven. Completion is tracked by Phase 13.2-13.3.
- [x] 10.4 Session tab: rewrite `RdpSessionTab` to embed `RdpDisplay` instead of external-process control panel.
- [x] 10.5 Certificate TOFU: FreeRDP certificate verify callback → Qt dialog → store thumbprint; match existing SSH host-key TOFU pattern.
- [x] 10.6 NLA authentication: pass credentials from Profile/Vault to FreeRDP settings struct; never on command line.
- [x] 10.7 Packaging: bundle `libfreerdp-client3.so` for AppImage; add `libfreerdp-client3` dependency for deb/rpm; include DLLs in Windows PyInstaller build.
- [x] 10.8 Tests: mock FreeRDP in `test_rdp_client.py`; headless Qt tests for `test_rdp_display.py`; update existing `test_rdp_backend.py` for new backend API.
- [x] 10.9 Advanced features: fullscreen toggle, Ctrl-Alt-Del injection, clipboard text sync (FreeRDP clipboard channel).
- [ ] 10.10 Documentation: update `INSTALL.md` (FreeRDP dep), `USER_GUIDE.md` (RDP section), `SECURITY_MODEL.md` (certificate handling), `DATA_MODEL.md` if needed.

Verification:

```bash
pytest tests/test_rdp_client.py tests/test_rdp_display.py tests/test_rdp_backend.py -q
ruff check src/openadmindesk/core/rdp_client.py src/openadmindesk/ui/rdp_display.py src/openadmindesk/core/rdp_backend.py src/openadmindesk/ui/rdp_session_tab.py
```

### Phase 10 completion criteria
- No subprocess calls to `xfreerdp` or `mstsc.exe` remain in RDP code paths
- RDP session renders inside `RdpSessionTab` as embedded widget
- Keyboard, mouse, resize work correctly
- Certificate TOFU dialog appears on first connect to new host
- NLA authentication uses vault credentials, not command-line arguments
- All builds include FreeRDP library (bundled or declared dependency)
- All existing and new RDP tests pass
- `ruff check` passes on all changed files

### Phase 10 status correction (2026-07-22)
Phase 10 is NOT complete until 10.3, 10.10 and corresponding Phase 13 ABI/frame/manual gates are closed; mock tests do not replace real FreeRDP smoke.

## Phase 11 - CI, Version, And Release Recovery

Goal: restore a verifiable CI/CD pipeline and synchronize project versioning before feature expansion.

- [x] diagnose public Actions failures and validate action majors;
- [x] restore local Ruff/full pytest baseline with references to 648 passed/1 xfailed;
- [x] restore tag/project version fail-closed guard and packaging contract tests;
- [x] prove direct imports after exact `poetry install --with dev`;
- [x] centralize application version and eliminate stale `__version__ = 0.1.0` duplicate (hardcoded duplicate eliminated and metadata/pyproject resolver tested);
- [x] add workflow validation/actionlint or equivalent and ensure CI Ruff covers `src tools tests` (evidence: explicit PyYAML + parsed YAML semantic contract tests, pinned Poetry, lock checks both jobs, Ruff src tools tests);
- [x] publish reviewed changes and confirm actual GitHub CI green (Commit: dd5d828, Run: 29855190951);
- [x] bump version and create annotated tag v0.1.4 under the no-rewrite policy; v0.1.3 untouched (commit 827197d);
- [x] verify actual release artifacts on GitHub runners.

Verification:
- `poetry run ruff check src tools tests` exit 0
- `xvfb-run --auto-servernum poetry run pytest -q` exit 0
- `poetry run python tools/build.py check` reports correct version
- GitHub Actions run for `main` is green
- Version centralization verified: runtime/package metadata and build artifacts report 0.1.4.
- Workflow hardening: poetry run pytest tests/test_ci_workflow.py -q required equivalent; actionlint .github/workflows/*.yml additionally when available. Neither may mask failure; unavailable optional actionlint documented, but semantic contract evidence allows current task complete.

Completion Criteria:
- All tasks marked [x]
- CI pipeline is green on GitHub
- Versioning is centralized and consistent across `pyproject.toml` and `src/openadmindesk/__init__.py`

Phase 11 is complete based on GitHub CI run 29858080376 and release run 29858758461.

## Phase 12 - Windows EXE Connection UX Stabilization

Goal: Resolve critical UX defects reported in Windows EXE distribution regarding credential persistence and RDP diagnostics.

- [x] diagnose three user reports and root causes;
- [x] runtime credential deep copy/unlock/one-time RDP;
- [x] visible RDP diagnostics/reconnect state;
- [x] invalidate ProfileStore all-list cache and clear stale filter;
- [x] regression tests/local 662 passed 1 xfailed/Ruff;
- [x] publish reviewed five-file fix and confirm GitHub CI green (Commit: 74f05a9, Run: 29951691994, URL: https://github.com/FASTCHIP/openadmindesk/actions/runs/29951691994);
- [x] produce next Windows artifact/build from fixed commit: GitHub Actions workflow_dispatch run 29963235722 succeeded for HEAD 9ae67c4 (direct parent reviewed Phase 12 fix 74f05a9); artifact windows-0.1.4 (ID 8546859383) uploaded.
- [ ] manually verify saved RDP unlock, one-time cancel/error, SSH immediate visibility and restart persistence on Windows EXE.

Verification:
- `poetry run ruff check src tools tests`
- `QT_QPA_PLATFORM=offscreen poetry run pytest -q`
- Manual verification on Windows EXE build.

Completion Criteria:
- All checklist items marked [x].
- Manual verification on Windows EXE confirms fixes.
- GitHub CI is green for the fix commit.

Phase 12 is currently active; terminal feature expansion deferred.

## Phase 13 - Stack Evidence And Runtime Stabilization (Planned, Not Active)

### Goal
Evidence-first stabilization RDP/SSH/terminal/CI, without speculative stack replacement.

### Execution gate
Phase 12 remains active; Phase 13 must not start automatically until Phase 12 completes or human explicitly reprioritizes.

### Source
Assessed useful subset of deleted STACK_IMPROVEMENTS draft; AUDIT_REMEDIATION_PLAN remains source of truth.

### Global boundaries
Execute exact order; one bounded pass at a time; <=3 named implementation/test files; docs and WORKLOG separate; no commit/push unless explicitly requested; no real-completion claims without matching evidence.

### Factual corrections/non-goals
- Python range `>=3.12,<3.14` already includes 3.13; do not raise minimum, only add compatibility CI later.
- Do not fork/replace pyte before separated parser/feed/render benchmarks prove need.
- Do not migrate Poetry->uv without measured installation/maintenance problem and approved migration plan.
- Keep Paramiko/PySide6/cryptography/argon2/SQLite baseline.
- SFTP separate transport remains current DECISIONS.md choice until lifecycle ownership is proven.
- Existing SFTP/ProfileStore/VaultManager executor close contracts/tests are already done; do not redo them as generic gc-only work.
- No arbitrary fixed SSH rate-limit task without automatic retry/abuse evidence; focus on in-flight guard, backpressure, lifecycle, redaction.

### Checklist
- [x] 13.0 Correct RDP source-of-truth and retire draft:
  - Phase 10.3 reopened, Phase 13 recorded, STACK draft deleted; no code claims.

- [ ] 13.1 FreeRDP ABI audit:
  - Pass files max 3: `src/openadmindesk/core/rdp_client.py`, `src/openadmindesk/platform/platform_utils.py`, `tests/test_rdp_client.py`.
  - Validate supported FreeRDP 3 version, symbols, ctypes signatures, callback lifetime, context ownership, connect/start/stop/free ordering; fail closed on mismatch.
  - Mock symbol tests plus real library discovery/symbol evidence; no frame implementation mixed into audit.
  - Focused checks: py_compile/ruff/pytest test_rdp_client/diff-check.

- [ ] 13.2 Implement frame pipeline in bounded passes:
  - Pass A max3: `src/openadmindesk/core/rdp_client.py`, `src/openadmindesk/ui/rdp_display.py`, `tests/test_rdp_client.py` — native framebuffer ownership/copy, detached QImage, worker->main signal, callback lifetime, bounded frame delivery.
  - Pass B max3: `src/openadmindesk/ui/rdp_display.py`, `src/openadmindesk/ui/rdp_session_tab.py`, `tests/test_rdp_display.py` — display/resize/disconnect/stale-frame behavior; preserve certificate/NLA/input/clipboard/fullscreen/CAD/error-copy/reconnect/close behaviors.
  - Optional extra runtime UX test must be a separate <=3-file fix pass, not scope creep.
  - Focused tests/ruff/pycompile/diff-check.

- [ ] 13.3 Real manual RDP frame verification:
  - Separate evidence/docs pass; use `docs/GUI_SMOKE_EVIDENCE.md`, WORKLOG separately.
  - Real FreeRDP 3 target checks: library load, first certificate prompt, NLA success/failure, visible changing frames, keyboard/mouse, resize, clipboard, disconnect/reconnect, bounded multi-minute run.
  - No completion from mocks only; record platform/library/build/artifact and blockers.

- [ ] 13.4 Fix SSH reader busy loop and outbound send, no asyncio migration:
  - Pass A max2: `src/openadmindesk/core/ssh_terminal_backend.py`, `tests/test_ssh_terminal_tab.py` — stop event, no idle hot loop, bounded wait, deterministic disconnect/join.
  - Pass B max3: `src/openadmindesk/core/ssh_terminal_backend.py`, `src/openadmindesk/ui/ssh_terminal_tab.py`, `tests/test_ssh_terminal_tab.py` — bounded outbound queue/writer ownership, partial sends, backpressure, reconnect/disconnect clearing; UI handlers never block on Channel.send.
  - Preserve host-key TOFU, vault auth prompting, macro/MultiExec/monitor/SFTP actions and all unrelated UI behavior.
  - Targeted pytest/ruff/pycompile/diff-check; add full headless pytest after both passes.

- [ ] 13.5 Add terminal benchmarks before any pyte decision:
  - Measurement-only pass: new `tests/bench_terminal_throughput.py` and existing `tests/test_terminal_widget.py`; do not modify production in measurement pass.
  - Separate measures: pure pyte parse, TerminalWidget.feed, paint/render, scrollback growth, memory; workloads 1MiB plain, ANSI, cursor movement, long lines, small vs large chunks.
  - Initially non-gating; record hardware/Python/PySide/pyte/chunk sizes and baseline.
  - Optimization passes generated only from evidence, each <=3 files. Candidate own-code areas may include deque scrollback, batching update/feed, cached fonts/style runs, but no preselected solution.
  - pyte fork/libvterm spike requires explicit ADR, compatibility corpus and measured target.

- [ ] 13.6 Add Python 3.13 CI compatibility while retaining 3.12:
  - Pass max2: `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`.
  - Test matrix 3.12/3.13; keep `requires-python >=3.12,<3.14`; release/build stays 3.12 until separately approved.
  - Require lock check, Ruff, full headless pytest, imports on both; actual GitHub green evidence. No dependency-manager migration.

- [ ] 13.7 Security logging audit in multiple bounded passes:
  - Split by SSH/SFTP, vault/profile, RDP/VNC/tunnels; never >3 implementation/test files in one pass.
  - Sentinel secret caplog tests; no password/passphrase/private key/profile serialization; separate user-safe message and diagnostic detail; structured logging.
  - Do not add rate limiting unless automatic retry/abuse evidence is first documented.
  - Targeted tests, Ruff, pycompile, diff-check; full security scan only where matching scope.

- [ ] 13.8 Thread/Qt lifecycle tests:
  - Pass A max3: `src/openadmindesk/core/ssh_terminal_backend.py`, `src/openadmindesk/ui/ssh_terminal_tab.py`, `tests/test_ssh_terminal_tab.py`.
  - Pass B max3: `src/openadmindesk/core/rdp_client.py`, `src/openadmindesk/ui/rdp_session_tab.py`, `tests/test_rdp_client.py` (display tests separate if needed).
  - SFTP UI lifecycle only if evidence shows gap; executor lifecycle already covered and should not be reimplemented.
  - Use QSignalSpy/thread completion/destroyed/weakref after deferred deletes/bounded timeout; gc.collect alone insufficient.
  - Repeated connect/disconnect/close; no live worker/QThread/callback after owner destruction.

- [ ] 13.9 Consider shared SSH/SFTP transport only after 13.4 and 13.8 PASS:
  - First separate ADR docs pass in docs/DECISIONS.md; no code before approval.
  - Design owner/lease abstraction, not exposed raw Transport: ownership, refcount/leases, terminal-first and SFTP-first close, reconnect invalidation, host-key, vault auto-lock, transfer cancellation, simultaneous failure.
  - Prototype pass max2: new `src/openadmindesk/core/shared_ssh_session.py` + new `tests/test_shared_ssh_session.py`.
  - Integration passes bounded <=3; UI wiring separate; fallback separate SFTP session retained until full evidence/manual smoke.
  - May be rejected after ADR/spike with recorded reasons.

### Explicit hold

- No pyte fork/replacement or Poetry->uv migration without benchmark/problem evidence, compatibility/migration plan, rollback and explicit human approval.

### Verification matrix and completion criteria
Every item has targeted checks above; code items require Ruff/pycompile/diff-check and targeted pytest; CI/lifecycle major gates require full headless pytest.
RDP completion requires real smoke evidence, not mocks.
Python 3.13 requires actual GitHub green for both matrix versions.
Shared transport requires ADR + lifecycle tests + fallback.
Phase complete only all accepted checkboxes closed, docs/WORKLOG updated in separate passes, no open CRITICAL/HIGH/MEDIUM reviewer findings, full relevant verification recorded.
Explicit remaining exclusions: pyte/uv not silently activated.

