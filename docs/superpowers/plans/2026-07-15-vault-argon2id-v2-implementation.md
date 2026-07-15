# Vault Argon2id v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

## Goal

Complete Phase 9.9b: Implement Argon2id v2 vault format with backward-compatible v1 unlock support. New vaults use Argon2id with default parameters (time_cost=2, memory_cost=19456 KiB, parallelism=1, hash_len=32, version=19). Existing v1 vaults remain readable and writable.

## Architecture

- **v2 Vault Structure**: version=2, salt (32 hex chars), kdf="argon2id", kdf_params (time_cost, memory_cost, parallelism, hash_len, version), password_hash (64 hex chars), accounts (list), created_at (ISO 8601), updated_at (ISO 8601)
- **v1 Vault Structure**: version="1.0", salt (32 hex chars), key_hash (16 hex chars), accounts (list), optional iv/ciphertext/kdf/kdf_params/created_at/updated_at
- **Backward Compatibility**: VaultManager.unlock() detects version and dispatches to _unlock_v1() or _unlock_v2()
- **Atomic Operations**: All account add/remove operations use snapshot-and-rollback pattern
- **Key Derivation**: v2 uses argon2.low_level.hash_secret_raw with Argon2Type.ID
- **Password Verification**: v2 uses HMAC-SHA256 verifier (derived_key → HMAC-SHA256(derived_key, context) → 64 hex chars)
- **Fail-Closed**: Empty salt/password_hash rejected before derivation; out-of-range parameters rejected; bool values rejected

## Tech Stack

- Python >=3.12,<3.14
- argon2-cffi>=23
- cryptography>=42
- No new dependencies required

## Global Constraints

1. Python >=3.12,<3.14
2. Argon2id defaults: time_cost=2, memory_cost=19456 KiB, parallelism=1, hash_len=32, version=19
3. New vault v2; v1 string "1.0" unlock/read/write remains
4. AES-GCM current account format and 12-byte nonce unchanged
5. 9.9c migration and 9.9d UI out of scope
6. Never log passwords/keys; no plaintext secret persistence
7. Protected: pyproject.toml, poetry.lock, generated files, migrations, UI
8. Expected source scope: src/openadmindesk/core/vault_format.py, src/openadmindesk/core/vault_manager.py, tests/test_vault_format.py, tests/test_vault_manager.py; docs WORKLOG/spec/plan
9. AUDIT plan checkbox only after every final gate
10. No automated commit/push; final success only READY_FOR_MANUAL_COMMIT

## Task 1: Read-only baseline and semantic inventory

**Files**: src/openadmindesk/core/vault_format.py, src/openadmindesk/core/vault_manager.py, tests/test_vault_format.py, tests/test_vault_manager.py, docs/AUDIT_REMEDIATION_PLAN.md

**Interfaces**:
- VaultFormat.create_empty_vault(version=LATEST_VERSION) → dict
- detect_version(data) → Optional[int]
- VaultManager.setup_master_password(str) → bool
- unlock(str) → bool
- _derive_key_v2(str, bytes, Optional[Dict[str,int]]) → bytes
- _compute_v2_verifier(bytes) → str

**Steps**:
- [ ] Run `git status --short`
- [ ] Run `git diff --stat`
- [ ] Run `git diff -- src/openadmindesk/core/vault_format.py src/openadmindesk/core/vault_manager.py tests/test_vault_format.py tests/test_vault_manager.py`
- [ ] Inspect docs/AUDIT_REMEDIATION_PLAN.md Phase 9.9b
- [ ] Map interfaces and validate against existing implementation
- [ ] Verify no unexpected files changed

**Expected Outcome**: Baseline snapshot of current WIP diff (modified WORKLOG, vault_format.py, vault_manager.py, test_vault_format.py, test_vault_manager.py), interface map, and scope confirmation. Any other file => SCOPE_VIOLATION and stop for restoration-only. Expected untracked `docs/superpowers/specs/` and `docs/superpowers/plans/` as expected docs; any other unexpected file still SCOPE_VIOLATION.

## Task 2: Acceptance coverage gaps only in tests/test_vault_manager.py

**Files**: Modify tests/test_vault_manager.py

**Interfaces**: Consumes existing VaultManager/Account APIs; Produces three acceptance behaviors: v2 account round-trip, v1 backward compatibility, Argon2 failure logging protection.

**Steps**:
- [ ] Step 1: Add `import logging` at existing import block (json, argon2 already present)
- [ ] Step 2: Add function A with setup+unlock before add; Account uses service_type and real fields; plaintext absent; fresh manager reads all three sensitive fields
```python
def test_v2_account_round_trip_survives_fresh_manager(tmp_path) -> None:
    vault_path = tmp_path / "vault.json"
    master_password = "master123"
    manager = VaultManager(str(vault_path))
    assert manager.setup_master_password(master_password)
    assert manager.unlock(master_password)

    account = Account(
        id="test-acc",
        name="Test Account",
        username="user",
        password="secret123",
        private_key="-----BEGIN TEST PRIVATE KEY-----\nkey-data",
        private_key_passphrase="keyphrase123",
        host="example.com",
        port=22,
        service_type="ssh",
    )
    assert manager.add_account(account)

    vault_text = vault_path.read_text(encoding="utf-8")
    assert "secret123" not in vault_text
    assert "keyphrase123" not in vault_text
    assert "-----BEGIN TEST PRIVATE KEY-----" not in vault_text

    manager.lock()
    reloaded = VaultManager(str(vault_path))
    assert reloaded.unlock(master_password)
    reloaded_account = reloaded.get_account("test-acc")
    assert reloaded_account is not None
    assert reloaded_account.password == "secret123"
    assert reloaded_account.private_key == "-----BEGIN TEST PRIVATE KEY-----\nkey-data"
    assert reloaded_account.private_key_passphrase == "keyphrase123"
```
- [ ] Step 3: EXTEND existing `test_v1_old_vault_still_unlocks_and_writable`; show ONLY append snippet after current assertions:
```python
    manager.lock()
    reloaded = VaultManager(str(vault_path))
    assert reloaded.unlock("v1password")
    reloaded_account = reloaded.get_account("v1_write")
    assert reloaded_account is not None
    assert reloaded_account.password == "secret"
```
No manual v1 dict, no replacement full test.
- [ ] Step 4: Add function C exactly using valid setup before monkeypatch:
```python
def test_v2_argon2_failure_does_not_log_master_password(tmp_path, caplog, monkeypatch):
    vault_path = tmp_path / "vault.json"
    setup_manager = VaultManager(str(vault_path))
    assert setup_manager.setup_master_password("setup-password")
    attempted_password = "testpassword123"
    def failing_hash(*args, **kwargs):
        raise argon2.exceptions.Argon2Error(
            f"simulated failure for {attempted_password}"
        )
    monkeypatch.setattr(argon2.low_level, "hash_secret_raw", failing_hash)
    manager = VaultManager(str(vault_path))
    with caplog.at_level(logging.ERROR, logger="openadmindesk.core.vault_manager"):
        result = manager.unlock(attempted_password)
    assert result is False
    assert attempted_password not in caplog.text
```
- [ ] Step 5: Run exact three node IDs command
`QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vault_manager.py::test_v2_account_round_trip_survives_fresh_manager tests/test_vault_manager.py::test_v1_old_vault_still_unlocks_and_writable tests/test_vault_manager.py::test_v2_argon2_failure_does_not_log_master_password -q --tb=short -p no:cacheprovider`
- [ ] Step 6: Run full test_vault_manager command
`QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vault_manager.py -q --tb=short -p no:cacheprovider`
- [ ] Step 7: If any command nonzero, report exact failure and stop before production edits

**Expected**: Both commands exit 0; characterization may pass immediately.

## Task 3: Independent diff/scope review

**Files**: All changed files from Task 1 baseline

**Interfaces**: Consumes original request, approved spec, acceptance criteria, and semantic diff; Produces reviewer verdict and severity-ranked findings.

**Steps:**
- [ ] Controller invokes deepseek-reviewer with original request, spec, acceptance criteria, summary and risks
- [ ] Reviewer inspects current semantic diff
- [ ] Confirmed CRITICAL/HIGH/MEDIUM findings → NEEDS_FIXES and one narrow correction task per finding
- [ ] Reject style/speculative/preexisting findings
- [ ] Reviewer PASS required

**Expected Outcome**: Reviewer PASS or specific findings with narrow correction tasks.

## Task 4: Targeted corrections

**Files**: Specific files named in Task 3 findings

**Interfaces**: Consumes confirmed finding with exact file/behavior/test; produces targeted correction+test evidence

**Steps**:
- [ ] For each confirmed finding, create narrow correction task
- [ ] Controller writes a mini-plan with exact patch/test after validating finding
- [ ] Implement correction
- [ ] Rerun targeted tests
- [ ] Reinvoke deepseek-reviewer for corrected files
- [ ] Max two cycles normally
- [ ] If no findings, skip

**Expected Outcome**: All findings resolved or rejected; reviewer PASS on corrected files.

## Task 5: Runtime verification

**Files**: All changed files

**Interfaces**: Consumes final reviewed working tree; Produces exact command, exit code, relevant output, and test counts for every check.

**Steps:**
- [ ] Run `python3 -m py_compile src/openadmindesk/core/vault_format.py src/openadmindesk/core/vault_manager.py tests/test_vault_format.py tests/test_vault_manager.py` (exit 0)
- [ ] Run `ruff check --no-cache src tools tests` (exit 0)
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vault_format.py tests/test_vault_manager.py -q --tb=short -p no:cacheprovider` (exit 0, report test count)
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider` (exit 0, report full test count)
- [ ] Run `poetry run bandit -r src/ -lll` (exit 0)
- [ ] Run `poetry run pip-audit` (exit 0)
- [ ] Run `git diff --check` (exit 0)
- [ ] Run `git status --short` (report only expected files)

**Expected Outcome**: All commands exit 0; no timeouts/hangs; actual counts reported.

## Task 6: Documentation completion

**Files**: docs/AUDIT_REMEDIATION_PLAN.md, docs/WORKLOG.md

**Interfaces**: Consumes final reviewer PASS and all Task 5 exit-0 evidence; Produces only 9.9b checkbox, final WORKLOG evidence, and READY_FOR_MANUAL_COMMIT.

**Steps:**
- [ ] Modify docs/AUDIT_REMEDIATION_PLAN.md: change `- [ ] 9.9b` to `- [x] 9.9b`
- [ ] Append concise WORKLOG final entry with:
  - Files changed
  - Exact commands
  - Exit codes/counts
  - Reviewer PASS
  - Remaining risk (9.9c migration excluded)
- [ ] Run `git diff --check`
- [ ] Inspect final status

**Expected Outcome**: Checkbox marked, WORKLOG updated, no whitespace issues, READY_FOR_MANUAL_COMMIT state.

## Plan Self-Review

**Spec Coverage**: Implementation covers v2 Argon2id with default parameters, v1 backward compatibility, atomic operations, fail-closed validation, and no plaintext secret logging.

**Placeholder-marker scan**: Clean; all steps are concrete and actionable.

**Interface Consistency**: Interfaces match existing VaultManager and VaultFormat contracts; no invented APIs.

**Scope Check**: Changes limited to vault format/manager and tests; no migration/UI work; no dependency changes; no broad refactors.

**Verification Strategy**: Targeted tests for v2 functionality, v1 compatibility, and security properties; full lint/test suite; security scans.

**Risk Mitigation**: Atomic operations with rollback prevent partial state; fail-closed validation prevents unsafe parameters; no plaintext secrets logged.
