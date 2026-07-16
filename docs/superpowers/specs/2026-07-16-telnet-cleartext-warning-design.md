# Telnet Cleartext Warning Design

## Status

Approved: 2026-07-16  
Date: 2026-07-16  
Dependency: Phase 9.10 in AUDIT_REMEDIATION_PLAN.md

## Goal

Implement a warning dialog that informs users about the insecure nature of Telnet connections before every connection attempt, including reconnects. The warning should be displayed only in the UI layer, without modifying the TelnetBackend.

## In/Out Scope

### In Scope
- Warning dialog displayed before every Telnet connection attempt
- Reconnect warning displayed before disconnecting and reconnecting
- Default "No" button behavior (cancel connection)
- UI-layer only implementation (TelnetBackend unchanged)
- Helper method `_confirm_cleartext_connection()` that returns bool
- Separated connection flow to prevent double-prompting on reconnect
- Dialog explicitly states credentials and session data are unencrypted
- Cancellation of initial connect leaves status/buttons/backend untouched
- Yes starts exactly once; reconnect Yes disconnects then starts exactly once
- No persisted suppression/settings
- Headless Qt tests with new test file in QT_TEST_FILES

### Out Scope
- Backend changes to TelnetBackend
- Persistent warning suppression
- Vault integration for warning preferences
- Any changes to the TelnetBackend class itself

## Rejected Alternatives

### Alternative 1: Persistent Warning Suppression
**Rejected:** The design explicitly states no persisted suppression/settings. This would require storing user preferences in the profile or settings, which is outside the scope.

### Alternative 2: Backend Warning Integration
**Rejected:** The design specifically requires UI-layer only implementation. Backend changes would violate this constraint.

### Alternative 3: Default "Yes" Behavior
**Rejected:** The design explicitly states default No behavior. This would change the security posture of the application.

## Architecture/Components

### Components
1. **TelnetSessionTab** - Modified to include warning dialog
2. **Warning Dialog** - Custom dialog with clear security warning
3. **Helper Method** - `_confirm_cleartext_connection()` that returns bool
4. **Connection Flow** - Separated start flow to prevent double-prompting

### Data Flow

#### Initial Connect Flow
1. User clicks "Connect" button
2. `_toggle_connection()` is called
3. If not connected, `_confirm_cleartext_connection()` is called
4. If confirmation returns False, connection attempt is cancelled
5. If confirmation returns True, `_start_connection()` is called
6. `_start_connection()` sets Connecting state, schedules backend connect
7. Connection proceeds normally

#### Reconnect Flow
1. User clicks "Reconnect" button
2. `_on_reconnect()` is called
3. `_confirm_cleartext_connection()` is called
4. If confirmation returns False, reconnect is cancelled
5. If confirmation returns True, `_disconnect()` is called, then `_start_connection()` is called
6. `_start_connection()` sets Connecting state, schedules backend connect
7. Connection proceeds normally

## Exact Architecture

- `_confirm_cleartext_connection() -> bool`: calls localized `QMessageBox.warning`; returns True only on Yes; catches dialog exception and returns False (fail closed)
- `_start_connection() -> None`: contains current existing body `_connect` after warning (sets Connecting, schedules backend connect); never confirms
- _connect() -> None: calls _confirm_cleartext_connection(); False returns with no UI/backend/signal changes; True calls _start_connection().
- `_on_reconnect() -> None`: confirm first; No returns preserving live session; Yes `_disconnect()` then `_start_connection()`; never calls `_connect()` and therefore no double prompt

## Exact Data Flows

### Initial Connect Flow
1. User clicks "Connect".
2. `_toggle_connection()` calls `_connect()` because the tab is disconnected.
3. `_connect()` calls `_confirm_cleartext_connection()`.
4. `No` or a dialog exception returns immediately without UI, backend, or signal changes.
5. `Yes` calls `_start_connection()` exactly once.

### Reconnect Flow
1. User clicks "Reconnect".
2. `_on_reconnect()` calls `_confirm_cleartext_connection()` before disconnecting.
3. `No` or a dialog exception returns immediately; the active connection and UI state are preserved.
4. `Yes` calls `_disconnect()` once and `_start_connection()` once.
5. `_on_reconnect()` never calls `_connect()`, so reconnect shows exactly one warning.
## Dialog Contract

### Call Form
`QMessageBox.warning(parent, title, body, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)`

### Title
`_("Telnet Connection Warning")`

### Body
`_("This connection uses the Telnet protocol, which transmits credentials and session data in plaintext over the network. Network observers can read your username, password, and all session data. Only use this connection type for trusted legacy systems.")`

### Buttons
- **Yes** - Proceed with connection
- **No** - Cancel connection attempt

### Default Button
"Cancel" (No) button is default

## UI State/Error Handling

### UI State
- Connection status labels and buttons are updated appropriately
- When warning dialog is shown, UI remains in a consistent state
- If user cancels, connection attempt is aborted and UI state is preserved

### Error Handling
- If dialog cannot be displayed, connection attempt is cancelled
- If connection fails for other reasons, appropriate error handling occurs
- All Qt threading boundaries are preserved

## Test Matrix

| Scenario | Expected Behavior |
|----------|------------------|
| User clicks "Connect" and selects "No" | Connection attempt cancelled, UI state preserved |
| User clicks "Connect" and selects "Yes" | Connection proceeds normally |
| User clicks "Reconnect" and selects "No" | Reconnect cancelled, UI state preserved |
| User clicks "Reconnect" and selects "Yes" | Disconnects, then connects normally |
| Dialog cannot be displayed | Connection attempt cancelled |

## Exact Expected Files

1. `src/openadmindesk/ui/telnet_session_tab.py` - Modified to include warning
2. `tests/test_telnet_session_tab.py` - New test file for Telnet session tab
3. `tests/conftest.py` - Updated to include new test file in QT_TEST_FILES
4. `docs/SECURITY_MODEL.md` - Updated to document the warning behavior
5. `docs/AUDIT_REMEDIATION_PLAN.md` - Updated to reflect completion of 9.10a
6. `docs/WORKLOG.md` - Updated with implementation details
7. `docs/superpowers/plans/2026-07-16-telnet-cleartext-warning-implementation.md` - Implementation plan
8. This specification file

## Verification Commands

```bash
python3 -m py_compile src/openadmindesk/ui/telnet_session_tab.py tests/test_telnet_session_tab.py
ruff check src/openadmindesk/ui/telnet_session_tab.py tests/test_telnet_session_tab.py tests/conftest.py
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_telnet_session_tab.py -q --tb=short -p no:cacheprovider
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider
git diff --check
```

## Acceptance Criteria

1. Warning dialog appears before every Telnet connection attempt
2. Dialog explicitly states plaintext transmission of credentials and session data
3. Default behavior is "No" (cancel connection)
4. Reconnect flow shows warning before disconnecting and reconnecting
5. No double-prompting on reconnect
6. UI state is preserved when connection is cancelled
7. Backend functionality remains unchanged
8. New tests pass
9. No persisted warning suppression
10. Reconnect "No" preserves backend connection and no status signal
11. Dialog exception does not call backend

## Remaining Risks

1. **Dialog Display Failure**: If Qt dialog cannot be displayed, connection is cancelled. This is acceptable as it maintains security posture.
2. **Threading Issues**: All Qt threading boundaries are preserved, but additional testing may be needed in complex scenarios.
3. **User Experience**: The warning may be perceived as intrusive by some users, but security is prioritized.

## Process Constraint

No commit/push actions. Protected existing Phase9.9d diff.
