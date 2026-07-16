# Telnet Cleartext Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require explicit acknowledgement of Telnet cleartext risk before every initial connection and reconnect.

**Architecture:** `TelnetSessionTab` owns the warning because it is a UI security decision. `_connect()` confirms and delegates to `_start_connection()`. `_on_reconnect()` confirms before disconnecting, then calls `_disconnect()` and `_start_connection()` directly, preventing a double prompt. `TelnetBackend` remains unchanged.

**Tech Stack:** Python 3.12+, PySide6/Qt6, pytest, ruff.

## Global Constraints

- Default response is `QMessageBox.No`; only explicit `Yes` proceeds.
- Warning title/body and buttons match the approved design spec exactly and pass through `_()`.
- Dialog exceptions fail closed with no UI/backend/signal changes.
- Reconnect cancellation preserves the active connection and UI state.
- No persisted suppression, backend changes, settings changes, dependency changes, or lockfile changes.
- Existing Phase 9.9d code/test/config paths are protected. Shared docs receive only the targeted additions listed below.
- No repository history operations are performed; final status is `READY_FOR_MANUAL_COMMIT`.

## File Map

- Modify `src/openadmindesk/ui/telnet_session_tab.py`: warning and separated connection flow.
- Create `tests/test_telnet_session_tab.py`: headless behavior tests.
- Modify `tests/conftest.py`: add `test_telnet_session_tab.py` to `QT_TEST_FILES`.
- Modify `docs/SECURITY_MODEL.md`: Telnet cleartext warning contract.
- Modify `docs/AUDIT_REMEDIATION_PLAN.md`: split 9.10 into 9.10a/9.10b/9.10c.
- Append `docs/WORKLOG.md`: plan and verified evidence.
- Preserve this plan and `docs/superpowers/specs/2026-07-16-telnet-cleartext-warning-design.md`.

## Task 1: Baseline and pre-edit record

- [ ] Read `AGENTS.md`, the approved spec, `telnet_session_tab.py`, `conftest.py`, and nearby tests.
- [ ] Run `git status --short`, `git diff --stat`, `git diff --name-status`, cached equivalents, and `git diff --check`; stop on unexpected paths.
- [ ] Run `ruff check src tests`.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider` and record the actual count.
- [ ] Append a short pre-edit Phase 9.10a plan entry to `docs/WORKLOG.md`, preserving all prior content.

## Task 2: TDD warning and flow tests

**Interfaces:** tests consume `TelnetSessionTab`, `Profile`, `SessionType`, `QMessageBox`, and `QTimer`; they produce no production helpers.

- [ ] Create `tests/test_telnet_session_tab.py` with a real profile fixture:

```python
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.ui.telnet_session_tab import TelnetSessionTab

TITLE = "Telnet Connection Warning"
BODY = (
    "This connection uses the Telnet protocol, which transmits credentials "
    "and session data in plaintext over the network. Network observers can "
    "read your username, password, and all session data. Only use this "
    "connection type for trusted legacy systems."
)

@pytest.fixture
def telnet_tab() -> TelnetSessionTab:
    profile = Profile(
        name="Legacy",
        host="legacy.example",
        port=23,
        username="admin",
        session_type=SessionType.TELNET,
    )
    return TelnetSessionTab(profile)
```

- [ ] Add `test_dialog_contract_defaults_to_no`: capture `QMessageBox.warning` positional arguments, return `No`, assert result is False and exact `(tab, TITLE, BODY, Yes|No, No)`.
- [ ] Add `test_initial_no_preserves_state`: snapshot `_connected`, status text/style, connect text/enabled, reconnect enabled; patch warning to `No` and `_start_connection` to fail if called; assert snapshots and emitted-signal list unchanged.
- [ ] Add `test_initial_yes_starts_once`: warning returns `Yes`; replace `_start_connection` with recorder; assert one call.
- [ ] Add `test_reconnect_no_preserves_active_session`: set `_connected=True`; warning returns `No`; `_disconnect` and `_start_connection` fail if called; assert state and signals unchanged.
- [ ] Add `test_reconnect_yes_prompts_disconnects_and_starts_once`: warning records one call and returns `Yes`; replace `_disconnect` and `_start_connection` with recorders; assert exactly one of each and one prompt.
- [ ] Add `test_dialog_exception_fails_closed`: warning raises `RuntimeError`; `_start_connection` fails if called; `_connect()` returns without mutation.
- [ ] Add `test_start_connection_runs_existing_backend_flow`: patch `QTimer.singleShot` with `lambda delay, callback: callback()`, patch `backend.connect` to return True, call `_start_connection()`, and assert connected UI state plus one `connection_status_changed(True)` signal.
- [ ] Add `"test_telnet_session_tab.py"` to `QT_TEST_FILES` in `tests/conftest.py`.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_telnet_session_tab.py -q --tb=short -p no:cacheprovider`; expected RED is missing `_confirm_cleartext_connection`/`_start_connection`, not a test harness or modal failure.
- [ ] Run `python3 -m py_compile tests/test_telnet_session_tab.py` and `ruff check tests/test_telnet_session_tab.py tests/conftest.py`.

## Task 3: Minimal production GREEN

**Interfaces produced:** `_confirm_cleartext_connection() -> bool`, `_start_connection() -> None`; existing `_connect()` and `_on_reconnect()` remain slots returning `None`.

- [ ] Add `QMessageBox` to the existing QtWidgets import.
- [ ] Add the fail-closed confirmation method:

```python
def _confirm_cleartext_connection(self) -> bool:
    try:
        response = QMessageBox.warning(
            self,
            _("Telnet Connection Warning"),
            _(
                "This connection uses the Telnet protocol, which transmits "
                "credentials and session data in plaintext over the network. "
                "Network observers can read your username, password, and all "
                "session data. Only use this connection type for trusted "
                "legacy systems."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
    except Exception:
        return False
    return response == QMessageBox.Yes
```

- [ ] Move the current `_connect()` body unchanged into `_start_connection()`.
- [ ] Replace `_connect()` with:

```python
def _connect(self) -> None:
    if not self._confirm_cleartext_connection():
        return
    self._start_connection()
```

- [ ] Replace `_on_reconnect()` with:

```python
def _on_reconnect(self) -> None:
    if not self._confirm_cleartext_connection():
        return
    self._disconnect()
    self._start_connection()
```

- [ ] Run the targeted test file with the exact headless command from Task 2; all tests must pass with no modal dialogs.
- [ ] Run `python3 -m py_compile src/openadmindesk/ui/telnet_session_tab.py tests/test_telnet_session_tab.py`.
- [ ] Run `ruff check src/openadmindesk/ui/telnet_session_tab.py tests/test_telnet_session_tab.py tests/conftest.py`.
- [ ] Run `git diff --check`.

## Task 4: Independent review and one conditional correction

- [ ] Provide the approved spec, complete diff, verification evidence, expected files, and protected paths to the read-only reviewer.
- [ ] Require review of exact default `No`, warning text, fail-closed exception handling, untouched initial cancellation, reconnect preservation, one prompt/disconnect/start, unchanged backend, Qt-safe tests, and scope.
- [ ] If the reviewer reports a confirmed CRITICAL/HIGH/MEDIUM defect, add one focused regression test, verify RED, apply the minimal fix, verify GREEN, and request one re-review.
- [ ] If no confirmed defect remains, proceed without code changes.

## Task 5: Documentation and final gate

- [ ] After behavior and review pass, add a concise Telnet cleartext subsection to `docs/SECURITY_MODEL.md` describing per-attempt warning, default `No`, fail-closed behavior, reconnect preservation, and unencrypted credentials/session data.
- [ ] Replace the single audit 9.10 line with `9.10a [x] Telnet cleartext warning`, `9.10b [ ] tunnel logging`, and `9.10c [ ] executor lifecycle`.
- [ ] Append implementation files, exact commands/exit codes/counts, reviewer verdict, remaining risk, and no-history-operation note to `docs/WORKLOG.md`.
- [ ] Run `python3 -m py_compile src/openadmindesk/ui/telnet_session_tab.py tests/test_telnet_session_tab.py`.
- [ ] Run `ruff check src tests`.
- [ ] Run the targeted test file with the exact headless command from Task 2.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider`.
- [ ] Run `git diff --check`, full status/stat/name-status, and cached equivalents; require only expected paths.
- [ ] Obtain final reviewer PASS and report `READY_FOR_MANUAL_COMMIT` without changing repository history.

## Plan Self-Review

- Spec coverage: warning contract, initial/reconnect flows, fail-closed behavior, state preservation, tests, docs, and verification are mapped.
- Type consistency: helper signatures and Qt constants match the approved spec.
- QTimer isolation: only the `_start_connection` behavior test executes the callback immediately; confirmation-flow tests replace `_start_connection`.
- Scope: no backend, profile, settings, dependency, or lockfile changes.
- Placeholder scan: no unresolved instructions.