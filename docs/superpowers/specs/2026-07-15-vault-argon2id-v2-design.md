# Phase 9.9b: Argon2id v2 Vault Specification

## Document Metadata

- **Date**: 2026-07-15
- **Phase**: 9.9b
- **Status**: Approved
- **Related**: Phase 9.9c (v1→v2 migration)
- **Dependencies**: Python >=3.12,<3.14, PySide6, argon2-cffi, cryptography

## Context and Goal

Phase 9.9b implements Argon2id as the new default key derivation function (KDF) for vault creation while maintaining backward compatibility with existing PBKDF2 v1 vaults. This addresses modern cryptographic best practices without breaking existing user data.

**Key objectives**:
1. New vaults use Argon2id with safe default parameters
2. Existing v1 vaults continue to work unchanged
3. No automatic migration (deferred to Phase 9.9c)
4. Fail-closed behavior on cryptographic errors
5. No secrets in logs or error messages

## Scope

### In Scope

- `vault_format.py`: v2 structural validation and empty vault creation
- `vault_manager.py`: Argon2id derivation, v2 unlock, v2 setup
- `vault_manager.py`: Dispatch logic for v1/v2 unlock
- `vault_manager.py`: v2 master password setup with rollback on failure
- `vault_manager.py`: HMAC-SHA256 verifier for v2
- Tests for v2 creation, unlock, tamper detection, parameter validation
- Tests for v1 backward compatibility

### Out of Scope

- Automatic v1→v2 migration (Phase 9.9c)
- UI upgrade prompts (Phase 9.9d)
- CLI migration tools (Phase 9.9c)
- Vault format version negotiation
- Multi-factor authentication
- Hardware security module integration

## Architecture

### Versioned Structure Validation

The `vault_format` module provides version-aware validation:

```python
# vault_format.py
LATEST_VERSION = 2
LEGACY_VERSION = "1.0"

REQUIRED_V2_KDF_KEYS = {"time_cost", "memory_cost", "parallelism", "hash_len", "version"}
```

- `create_empty_vault(version=LATEST_VERSION)` creates v2 template
- `create_empty_vault(version=LEGACY_VERSION)` creates v1 template (backward compat)
- `_validate_v2()` enforces exact kdf_params keys, integer types, and hex shape validation
- `VaultManager` validates safe numeric bounds and Argon2 version before derivation

### VaultManager Dispatch

The `VaultManager` class handles version dispatch:

```python
class VaultManager:
    def setup_master_password(self, password: str) -> bool:
        # Creates v2 vault by default

    def unlock(self, password: str) -> bool:
        # Dispatches to _unlock_v1 or _unlock_v2 based on vault version

    def _unlock_v1(self, password: str) -> bool:
        # PBKDF2 unlock

    def _unlock_v2(self, password: str) -> bool:
        # Argon2id unlock with parameter validation
```

### AES-GCM Preservation

- Encryption cipher remains AES-GCM (256-bit)
- Key derivation changes from PBKDF2 to Argon2id
- Nonce generation: 12 random bytes for AES-GCM
- No changes to encrypted account data format

## v2 Data Flow

### Vault Structure

```json
{
  "version": 2,
  "kdf_params": {
    "time_cost": 2,
    "memory_cost": 19456,
    "parallelism": 1,
    "hash_len": 32,
    "version": 19
  },
  "salt": "32_character_hex_string",
  "password_hash": "64_character_hex_string",
  "accounts": [...],
  "created_at": "ISO_8601_timestamp",
  "updated_at": "ISO_8601_timestamp"
}
```

### Key Derivation Flow

1. **Salt generation**: 16 random bytes → 32-character hex string
2. **Argon2id parameters**:
   - time_cost: 2 iterations (adjustable)
   - memory_cost: 19456 KiB (adjustable)
   - parallelism: 1 thread (adjustable)
   - hash_len: 32 bytes (AES-256 key)
   - version: 19 (argon2-cffi constant)
3. **Derivation**: `argon2.low_level.hash_secret_raw(secret=password.encode(), salt=salt_bytes, type=Type.ID, version=19, ...)`
4. **Key extraction**: Full 32 bytes for AES-GCM
5. **Verifier**: HMAC-SHA256 of derived key → 64-character hex string

### Unlock Flow

1. Read vault JSON
2. Validate version (must be 2)
3. Validate kdf_params keys (exact set required)
4. Validate kdf_params types (integers, not booleans)
5. Validate kdf_params bounds (time_cost ≥ 1, memory_cost ≥ 8192, etc.)
6. Validate salt (32 hex characters)
7. Validate password_hash (64 hex characters)
8. Derive key using Argon2id with validated parameters
9. Compute HMAC-SHA256 of derived key
10. Compare with stored password_hash (constant-time)
11. On success: decrypt accounts with derived key
12. On failure: return False, no error details

### Setup Flow

1. Generate 16 random bytes for salt
2. Store salt as 32-character hex string
3. Derive key from password + salt using Argon2id
4. Compute HMAC-SHA256 verifier
5. Store verifier as 64-character hex string
6. Create empty accounts array
7. Set timestamps
8. Write vault JSON atomically (mode 0600)
9. On any failure: restore previous state

## Error Handling and Fail-Closed Behavior

### Cryptographic Failures

- `argon2.exceptions.Argon2Error`: Any Argon2 exception → return False, no details logged
- Wrong password: HMAC verification fails (constant-time compare) → return False
- Invalid parameters: Rejected before derivation → return False

### Parameter Validation

Reject with False (no manager-state or vault-file mutation):
- Missing kdf_params keys
- Extra kdf_params keys
- Boolean kdf_params values
- Out-of-bounds values (time_cost < 1, memory_cost < 8192, etc.)
- Wrong Argon2 version
- Invalid hex strings for salt/password_hash
- Wrong length hex strings

### Tamper Detection

- Salt tampering: HMAC verification fails → return False
- Password hash tampering: HMAC verification fails → return False
- Structure tampering: Validation fails → return False

### Logging

- Never log passwords, salts, or derived keys
- Never log full error messages from cryptographic failures
- Use generic messages: "Vault unlock failed", "Vault setup failed"
- Log parameter validation failures with safe parameter names only

## Acceptance Criteria

### Functional Requirements

1. **v2 create**: `setup_master_password()` creates v2 vault with Argon2id
2. **v2 unlock**: `unlock()` with correct password returns True for v2 vault
3. **v2 wrong password**: `unlock()` with wrong password returns False for v2 vault
4. **v2 tamper detection**: Tampered salt/password_hash returns False
5. **v2 unsafe parameters**: Invalid kdf_params returns False without mutation
6. **v2 unknown version**: Version ≠ 1,2 returns False
7. **Argon2 error rollback**: Argon2 failure during setup restores previous state
8. **v2 account round-trip**: Encrypt/decrypt account with v2 vault succeeds
9. **v1 unlock compatibility**: v1 vaults unlock with existing PBKDF2
10. **v1 read/write compatibility**: v1 vaults can read/write accounts

### Security Requirements

11. **No secrets in logs**: No passwords, salts, or keys in log output
12. **Fail-closed**: All errors return False, no partial state
13. **Constant-time comparison**: HMAC verification uses constant-time compare
14. **Safe defaults**: Argon2 parameters meet current security guidelines
15. **Atomic write**: Vault writes use atomic file operations
16. **File permissions**: Vault file mode 0600
17. **Save-failure rollback**: On save failure, restore prior vault state and updated_at timestamp

### Code Quality Requirements

18. **py_compile**: All modified Python files compile without syntax errors
19. **ruff check**: All modified files pass ruff linting
20. **bandit -lll**: No high-severity security issues in modified files
21. **pip-audit**: No known vulnerabilities in dependencies
22. **pytest targeted**: Vault format and manager tests pass
23. **pytest full**: Full headless test suite passes
24. **git diff --check**: No whitespace errors in changes
25. **Reviewer PASS**: Code review passes without CRITICAL/HIGH/MEDIUM findings

## Implementation Scope

### Files to Modify

1. `src/openadmindesk/core/vault_format.py`
2. `src/openadmindesk/core/vault_manager.py`
3. `tests/test_vault_format.py`
4. `tests/test_vault_manager.py`

### Files NOT to Modify

- `pyproject.toml`
- `poetry.lock`
- Generated files
- Migration scripts
- UI files (Phase 9.9d)

### Expected Changes

- **vault_format.py**: Add v2 validation, LATEST_VERSION constant, create_empty_vault version parameter
- **vault_manager.py**: Add Argon2id derivation, v2 unlock, v2 setup, dispatch logic, rollback on failure
- **test_vault_format.py**: Add v2 validation tests, update existing tests for version awareness
- **test_vault_manager.py**: Add v2 manager tests, update existing tests for v2 defaults

### Scope Clarification

The implementation scope for Phase 9.9b includes:
- Four Python/test files: `src/openadmindesk/core/vault_format.py`, `src/openadmindesk/core/vault_manager.py`, `tests/test_vault_format.py`, `tests/test_vault_manager.py`
- This specification document
- WORKLOG entry for this task
- AUDIT_REMEDIATION_PLAN checkbox update after all acceptance criteria are verified

Protected files that must not be modified:
- `pyproject.toml`
- `poetry.lock`
- Generated files
- Migration scripts
- UI files (Phase 9.9d)

## Testing Strategy

### Unit Tests

- v2 validation tests for vault format
- v2 manager tests for Argon2id derivation and unlock
- Backward compatibility tests for v1 vaults

### Integration Tests

- v2 account encryption/decryption round-trip
- v1 backward compatibility
- Mixed v1/v2 vault operations
- Error scenarios and rollback

### Security Tests

- Tamper detection (salt, password_hash)
- Parameter validation (bounds, types)
- Fail-closed behavior
- No secret leakage

## Verification Plan

### Pre-Implementation

1. Review specification for completeness
2. Confirm scope boundaries with controller

### During Implementation

1. Run `python3 -m py_compile` on modified files after each logical change
2. Run `ruff check` on modified files after each logical change
3. Run targeted tests after each logical change
4. Verify git diff --check after each logical change

### Final Verification

```bash
# Syntax check
python3 -m py_compile src/openadmindesk/core/vault_format.py src/openadmindesk/core/vault_manager.py tests/test_vault_format.py tests/test_vault_manager.py

# Linting
ruff check src/openadmindesk/core/vault_format.py src/openadmindesk/core/vault_manager.py tests/test_vault_format.py tests/test_vault_manager.py

# Targeted tests
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vault_format.py tests/test_vault_manager.py -q

# Full test suite
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider

# Security scans
poetry run bandit -r src/ -lll
poetry run pip-audit

# Git hygiene
git diff --check
git diff --stat
```

### Expected Results

- All syntax checks: exit code 0
- All linting: exit code 0
- Targeted tests: exit code 0
- Full tests: exit code 0
- Bandit: No high-severity issues
- pip-audit: No known vulnerabilities
- Git diff: Clean, no whitespace errors

## Risk Assessment

### Known Risks

1. **Argon2 availability**: argon2-cffi must be installed
   - Mitigation: Document dependency in pyproject.toml
   - Detection: Import error at module level; no graceful handling at runtime

2. **Parameter tuning**: Defaults may need adjustment
   - Mitigation: Use conservative defaults (2 iterations, 19456 KiB, parallelism 1)
   - Future: Make configurable in Phase 9.9d

3. **Performance impact**: Argon2 is slower than PBKDF2
   - Mitigation: Acceptable for security; can optimize in future
   - Current: 2 iterations with 19456 KiB is reasonable for desktop

### Mitigation Strategy

- Project metadata and import/package verification must detect a missing argon2-cffi dependency before runtime use
- Provide clear error messages (without secrets)
- Document performance characteristics
- Allow parameter adjustment in future phases

## Follow-up Work

### Phase 9.9c (Excluded from this scope)

- v1→v2 migration tool
- Backup/restore primitives
- Rollback capabilities
- CLI activation

### Phase 9.9d (Future)

- UI upgrade prompts
- Parameter configuration
- Migration status indicators
- Progress feedback

## References

- [Argon2 specification](https://www.ietf.org/rfc/rfc9109.html)
- [AUDIT_REMEDIATION_PLAN.md](../../AUDIT_REMEDIATION_PLAN.md)
- [WORKLOG.md](../../WORKLOG.md)

## Glossary

- **KDF**: Key Derivation Function
- **Argon2id**: Hybrid version of Argon2 algorithm
- **HMAC-SHA256**: Hash-based Message Authentication Code
- **Fail-closed**: System defaults to secure state on errors
- **Atomic write**: File operation that cannot be partially written
