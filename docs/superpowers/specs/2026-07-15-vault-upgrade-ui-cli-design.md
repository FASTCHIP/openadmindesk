# Phase 9.9d: Vault Upgrade UI & CLI Design

- **Date**: 2026-07-15 / **Phase**: 9.9d / **Status**: Approved
- **Depends on**: Phase 9.9c commit `6d56b61` (`upgrade_vault_v1_to_v2()` in `openadmindesk.core.vault_upgrade`)

Phase 9.9d provides user-visible surfaces for the 9.9c vault upgrade API:

1. **Qt menu action** (`Vault → Upgrade Vault Security…`) for interactive use.
2. **Standalone CLI** (`openadmindesk-vault-upgrade`) for headless/scripted use.
3. **Safety guards**: read-only version probe, exclusive-writer warning, confirmation dialogs, secure password prompts.

**Key objectives**: user-initiated only; CLI works without Qt; no secrets in args/logs/stdout; vault remains locked after upgrade.

### In Scope

- `vault_upgrade.py`: new `inspect_vault_version(path) -> int` (read-only probe, regular-file check, `detect_version` + `VaultFormat.validate_vault_format`)
- `vault_upgrade_cli.py`: new module with `main(argv=None) -> int`, argparse, password acquisition, text/json output
- `pyproject.toml`: new `[project.scripts]` entry `openadmindesk-vault-upgrade`
- `main_window.py`: new `Upgrade Vault Security…` action + `_on_upgrade_vault()` slot
- Tests: `test_vault_upgrade.py` (probe), `test_vault_upgrade_cli.py` (new), `test_main_window.py` (upgrade slot)
- Docs: `SECURITY_MODEL.md`, `VAULT_SPEC.md`, `AUDIT_REMEDIATION_PLAN.md`, `WORKLOG.md`

### Out of Scope

- Automatic startup/login/unlock prompts. Batch upgrade. Password change separate from upgrade.
- `AccountManager`/`VaultManager` refactoring.
- CLI `--password`/`--master-password`/`-p` args (secrets never in argv).
- `--dry-run` (probe is already read-only).
- Encrypted backup restoration tooling.
- Dependency or lockfile changes.

### Rejected Alternatives

- **Application `--upgrade-vault` flag**: current app lazily imports Qt after early checks, so this flag would not require Qt init. Rejected because it couples maintenance CLI parsing/output/exit semantics to desktop+Qt argument passthrough and is less isolated/testable than a separate command.
- **Source-only tool**: discovery-hostile, inconsistent with project conventions. Rejected.

## Architecture

Both entry points share the same core layer:

```
┌──────────────────────┐   ┌──────────────────────────────┐
│  MainWindow           │   │  vault_upgrade_cli.py        │
│  Vault→Upgrade…       │   │  (argparse, no PySide6)     │
│  _on_upgrade_vault()  │   │  main(argv) → int            │
└─────────┬────────────┘   └────────────┬─────────────────┘
          │                              │
          └─────────────┬────────────────┘
                        ▼
          ┌──────────────────────────┐
          │  vault_upgrade.py        │
          │  probe: inspect_vault_   │
          │         version(path)    │
          │  action: upgrade_vault_  │
          │          v1_to_v2(path,  │
          │          master_password)│
          └──────────────────────────┘
```

### Data Flow

1. **Probe first** — every code path calls `inspect_vault_version()` before any password interaction.
2. **v2 detected** → idempotent exit (info dialog / success text), no password requested.
3. **v1 detected** → proceed to confirmation (UI warning / CLI `--confirm-upgrade`).
4. **Password acquisition**: UI uses `QInputDialog.getText(echo=QLineEdit.Password)`; CLI uses `$OPENADMINDESK_VAULT_PASSWORD` env var first, `getpass.getpass()` fallback only on interactive TTY.
5. **Core call**: `upgrade_vault_v1_to_v2(Path(vault_path), password)` — synchronous, main thread.
6. **Result handling**: `VaultUpgradeResult` fields or `VaultUpgradeError` metadata mapped to user-facing messages. UI never shows hashes; CLI JSON intentionally includes result/error hash metadata for scripting consumers; neither path prints secrets.

No automatic flow, no background workers, no startup probe.

## Core API (vault_upgrade.py)

### Existing 9.9c (committed at `6d56b61`)

| Item | Signature / Fields |
|------|--------------------|
| Core function | `upgrade_vault_v1_to_v2(path: Path, master_password: str) -> VaultUpgradeResult` |
| `VaultUpgradeResult` | `source_version: int`, `target_version: int`, `accounts_reencrypted: int`, `source_sha256: str`, `target_sha256: str`, `backup_deleted: bool`, `retained_backup_path: Optional[str]` |
| `VaultUpgradeError` | `message`, metadata: `rollback_succeeded: Optional[bool]`, `recovery_backup_path: Optional[str]`, `source_sha256: Optional[str]`, `backup_sha256: Optional[str]` |

Same password for v1 decrypt and v2 re-encrypt. No `old_password`/`new_password` distinction.

### NEW in 9.9d — `inspect_vault_version(path: Path) -> int`

- Opens `path` as **UTF-8 JSON text** for read-only access.
- Validates the file is a regular file via `lstat`/`S_ISREG`, rejecting symlink, directory, FIFO, device, and any other non-regular path — raises `VaultUpgradeError`.
- Parses JSON, calls `detect_version()` for version discrimination:
  - Version field `"1.0"` (string) → returns `1`.
  - Version field `2` (int) → returns `2`.
  - Anything else → raises `VaultUpgradeError`.
- Calls `VaultFormat.validate_vault_format()` for structural validation on known versions.
- Returns `1` or `2`; raises `VaultUpgradeError` for any invalid, unreadable, or unknown state.
- **Side-effect-free**: no modification of file bytes, mtime, mode, or inode.
- **Callers must not reimplement version detection or parse vault JSON directly** — this function is the single source of truth.

## UI Design (MainWindow)

### Menu Item Placement

Existing Vault menu order: `Setup Master Password…`, `Unlock Vault…`, `Lock Vault`, separator, `Manage Accounts…`.

**Insert `Upgrade Vault Security…` before the separator** (between Lock Vault and the separator above Manage Accounts). No accelerator shortcut. No `Change Password` action exists.

The action is always enabled (the probe determines the vault state; there is no pre-check at startup to avoid side effects or latency).

### `_on_upgrade_vault()` Flow

1. **Probe**: `inspect_vault_version(Path(self.vault_manager.vault_path))`
   - Error → `critical("Could not read vault file:\n{error}")` → return.
   - v2 → `information("Already using v2.")` → return.
   - v1 → continue.

2. **Warning** (v1 only): `warning("This will upgrade to v2. A backup will be created. Only proceed if no other instance is using this vault. Continue?")` → No/ESC return; Yes continue.

3. **Re-lock** (only if `self.vault_manager.is_unlocked()`): `question("Vault will be locked before upgrade. You will need to re-enter your master password. Continue?")` → No/ESC return (stays unlocked); Yes → `self.vault_manager.lock()` → set `self._last_vault_unlocked = False` → `self._update_vault_menu()` (must **not** call `self._lock_vault()`, whose generic status message would mask the flow lock). This explicit `_last_vault_unlocked` reset prevents the poll timer in `_poll_vault_lock_state()` from emitting a spurious `Vault auto-locked` notification. Already-locked vaults skip this step entirely.

4. **Password**: `QInputDialog.getText(echo=QLineEdit.Password)` → Cancel or empty password returns without core call (if locked in step 3, vault stays locked); OK continues.

5. **Core call** (synchronous): `upgrade_vault_v1_to_v2(Path(...), password)`

   | Outcome | UI response |
   |---------|-------------|
   | Error (pre-replace) or `rollback_succeeded=None` | `critical(str(error) + "\n\nSource was not replaced.")` (+ recovery backup path if non-null); no secret in message |
   | Error + `rollback_succeeded=True` | `warning("Original v1 restored.")` (+ recovery path if non-null) |
   | Error + `rollback_succeeded=False` | `critical("Rollback failed.")` (+ recovery path if non-null) |
   | Result + `backup_deleted=True` | `information("Upgraded to v2. Backup removed.")` |
   | Result + `backup_deleted=False` | `warning("Upgraded to v2.")` (+ path if non-null), else generic retained-backup warning |

6. Vault remains locked after step 5 regardless of outcome. No hashes displayed. Cancel or empty password after step 3 lock leaves vault locked.

## CLI Design (vault_upgrade_cli.py)

**Module**: `src/openadmindesk/vault_upgrade_cli.py` — no PySide6/Qt import.
**Entry point**: `openadmindesk-vault-upgrade = "openadmindesk.vault_upgrade_cli:main"`
**Signature**: `main(argv: Optional[list[str]] = None) -> int` (uses argparse; `None` → `sys.argv[1:]`)

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--vault` | `platform_utils.default_vault_path()` | Path to vault JSON file |
| `--password-env` | `OPENADMINDESK_VAULT_PASSWORD` | Env var name holding password |
| `--confirm-upgrade` | `False` (store_true) | Acknowledge v1->v2 upgrade |
| `--format` | `"text"` (`text`/`json`) | Output format |

**Explicitly NOT an argument**: `--password`, `--master-password`, `-p` (never in argv).

### Execution Flow (Exact Order)

```
1. Parse arguments.
   ├─ argparse error → text stderr, exit 2.
   └─ OK → continue.

2. Resolve vault path (from --vault or default).
   ├─ Missing / not a file → stderr "Error: ...", exit 1.
   └─ exists → continue.

3. Probe: inspect_vault_version(path)
   ├─ VaultUpgradeError → stderr/text or JSON stdout, exit 1.
   ├─ Returns 2 → stdout text/json, exit 0.
   └─ Returns 1 → continue.

4. (Only if probe == 1)
   If not --confirm-upgrade:
     text stderr or JSON stdout per format; exit 2.

5. Acquire password:
   a. If $OPENADMINDESK_VAULT_PASSWORD (or --password-env override)
      is set and non-empty → use that value.
   b. Else if sys.stdin.isatty() → getpass.getpass("Master password: "). Empty→unusable, exit 2.
   c. Else → text stderr or JSON stdout per format; exit 2.

6. result = upgrade_vault_v1_to_v2(path, password)
   ├─ VaultUpgradeError → text stderr or JSON stdout per format; exit 1.
    └─ VaultUpgradeResult → text stdout or JSON stdout; exit 0.
 ```

Note: the v2-probe exit path (step 3, returns 2) does not read environment variables, call `getpass`, or require `--confirm-upgrade`.

Note on `sys.stdin.isatty()` (step 5b): this is a deliberate conservative gate. Although `getpass.getpass()` may open `/dev/tty` directly on Unix (bypassing stdin), the `isatty()` check on `sys.stdin` ensures that piped or non-TTY stdin configurations will **not** attempt an interactive prompt. Users in such environments must supply the password via `OPENADMINDESK_VAULT_PASSWORD` (or `--password-env` override) or the CLI exits with code 2. This avoids hangs or confusing output in headless/scripted pipelines.

### Exit Code Contract

| Code | Meaning |
|------|---------|
| `0` | Upgraded (v1→v2) or already v2 |
| `1` | Operational error (invalid vault, wrong password, corrupt file, rollback failure) |
| `2` | Usage/precondition error (argparse error, missing `--confirm-upgrade`, no password source) |

### Output Formats

#### `--format text` (default)

| Outcome | Stdout | Stderr |
|---------|--------|--------|
| Upgraded | `Vault upgraded from v1 to v2. Accounts re-encrypted: N` (and backup line if retained) | — |
| Already v2 | `Vault is already using the latest format (v2).` | — |
| Error | — | `Error: {message}` (+ rollback status + recovery path if non-null). No hashes/secrets. |

If `backup_deleted` is True, the backup line is omitted. If False, a line like `Backup retained: {path}` is shown.

#### `--format json`

Single JSON object to stdout even on non-zero exit. Standard argparse errors (unrecognized flags, etc.) always go to text on stderr at exit 2 regardless of `--format`.

**Upgraded (exit 0)**:
```json
{"status":"upgraded","source_version":1,"target_version":2,
 "accounts_reencrypted":7,"source_sha256":"<hex>","target_sha256":"<hex>",
 "backup_deleted":false,"retained_backup_path":"/path/to/backup"}
```

**Already current (exit 0)**:
```json
{"status":"already_current","source_version":2,"target_version":2}
```

**Error (operational exit 1 or parsed precondition exit 2)** — null where unavailable:
```json
{"status":"error","error":"<message>","rollback_succeeded":null,
 "recovery_backup_path":null,"source_sha256":null,"backup_sha256":null}
```

## Test Plan

### Test Matrix

| Area | Tests |
|------|-------|
| Core probe | `inspect_vault_version` returns 1 for v1 fixture, 2 for v2 fixture; raises `VaultUpgradeError` for invalid data, symlink path, unreadable file; does not modify file (mtime, content, mode) |
| CLI | Already v2 → exit 0, text/json output matches schema |
| CLI | v1 without `--confirm-upgrade` → exit 2 |
| CLI | v1 with `--confirm-upgrade` + env password → exit 0 on success, exit 1 on wrong password |
| CLI | No password source (no env, non-TTY stdin) → exit 2 |
| CLI | `--format json` produces parseable JSON on stdout |
| CLI | Module does not import PySide6 (verified via `sys.modules` check) |
| CLI | Wrong password → exit 1, error JSON has `status:"error"` |
| CLI | Empty getpass → exit 2, text stderr / JSON stdout |
| CLI | Error text with recovery metadata → stderr shows rollback + path, no hashes/secrets |
| UI | Probe `VaultUpgradeError` → critical dialog shown, `upgrade_vault_v1_to_v2` not called |
| UI | Already v2 → info dialog shown, no core call |
| UI | v1 warning → cancel → no core call |
| UI | v1 → confirm → unlocked → re-lock prompt → cancel → no core call (vault stays unlocked) |
| UI | v1 → confirm → unlock → re-lock consent → lock → password cancel → vault stays locked, no call |
| UI | Full flow (v1 → confirm → lock → password → core call) → `upgrade_vault_v1_to_v2` called exactly once with exact args `upgrade_vault_v1_to_v2(Path(expected_vault_path), entered_password)` |
| UI | Full flow relock assertions → `_last_vault_unlocked is False`, menu state synced; subsequent `_poll_vault_lock_state()` does **not** emit `Vault auto-locked` |
| UI | Wrong password / pre-replace error → critical with controlled `str(error)` + source not replaced, no secret in message |
| UI | Success `backup_deleted=True` → info with "Backup removed" |
| UI | Success `backup_deleted=False` → warning with backup path |
| UI | Error + `rollback_succeeded=True` → warning with recovery path (if non-null) |
| UI | Error + `rollback_succeeded=False` → critical with recovery path (if non-null) |
| UI | Empty password → no core call (stays locked if locked by relock consent) |

### Test Harness Rules

- Core and CLI tests: no Qt dependency, display-independent.
- CLI tests: invoke `main(argv=[...])` directly; capture stdout/stderr via `capsys`.
- UI tests: mock `QMessageBox`, `QInputDialog`, `inspect_vault_version`, and `upgrade_vault_v1_to_v2`. Use headless-safe harness (`QT_QPA_PLATFORM=offscreen`), no event loop blocking.
- All tests verify the exact call count to `upgrade_vault_v1_to_v2` (0 or 1 depending on cancellation).
- No secrets or passwords appear in test output, logs, or assertion messages.

## Verification Strategy

| Check | Command / Method | Expected |
|-------|------------------|----------|
| Syntax | `python3 -m py_compile src/openadmindesk/core/vault_upgrade.py src/openadmindesk/vault_upgrade_cli.py tests/test_vault_upgrade.py tests/test_vault_upgrade_cli.py tests/test_main_window.py` | Exit 0 |
| Lint | `ruff check src tests/` | No errors |
| Security (core) | `bandit -r src/openadmindesk/core/vault_upgrade.py` | Exit 0, no findings |
| Security (CLI) | `bandit -r src/openadmindesk/vault_upgrade_cli.py` | Exit 0, no findings |
| Probe tests | `pytest tests/test_vault_upgrade.py -q` | Pass |
| CLI tests | `pytest tests/test_vault_upgrade_cli.py -q` | Pass |
| UI tests | `pytest tests/test_main_window.py -q -k upgrade` | Pass |
| Full suite | `pytest tests/ -q` (headless, no `--timeout` flag, no `pytest-timeout` plugin) | Pass |
| Build (unique tmpdir) | `python3 -m build --wheel --outdir "$(mktemp -d)"` | Exit 0, wheel created |
| Entry point | Inspect `entry_points.txt` in built wheel for `openadmindesk-vault-upgrade` | Present |
| Diff whitespace | `git diff --check` | No whitespace errors |
| Scope gate | `git status --short` | Matches exact expected file list |
| Scope | `git diff --stat` | Only expected files |
| Review | Independent reviewer signs off all changes | PASS |

## Files Expected to Change

- `src/openadmindesk/core/vault_upgrade.py` — add `inspect_vault_version()`
- `src/openadmindesk/vault_upgrade_cli.py` — **NEW**
- `src/openadmindesk/ui/main_window.py` — add action + slot
- `pyproject.toml` — add console script
- `tests/test_vault_upgrade.py` — add probe tests
- `tests/test_vault_upgrade_cli.py` — **NEW**
- `tests/test_main_window.py` — add upgrade slot tests
- `docs/SECURITY_MODEL.md`, `docs/VAULT_SPEC.md`, `docs/AUDIT_REMEDIATION_PLAN.md`, `docs/WORKLOG.md`

## Remaining Risks and Limitations

- **Exclusive-writer requirement**: `upgrade_vault_v1_to_v2()` has no file locking. UI warning + CLI `--confirm-upgrade` are the caller's acknowledgement.
- **Encrypted backup retention**: If backup deletion fails, the encrypted backup remains at `retained_backup_path`. The core rollback can restore from it. No in-band cleanup.
- **Same-password only**: The current API uses the same password for v1 decrypt and v2 encrypt. A future phase may add a combined upgrade+password-change flow.

## Process Constraint

This is a **design document only**. No code, test, config, or audit file changes have been made. No commit or push has been performed.

**Next step**: write an implementation plan. Then implement per specification, run all verification, and report `READY_FOR_MANUAL_COMMIT`.
