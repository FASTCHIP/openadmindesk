# Vault Upgrade UI and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver user-visible surfaces for the 9.9c vault upgrade API: a Qt menu action (`Vault → Upgrade Vault Security…`) and a standalone CLI (`openadmindesk-vault-upgrade`), plus a read-only version probe, with safety guards and no secrets in arguments/logs/stdout.

**Architecture:** Both entry points share `inspect_vault_version(path)→int` (new read-only probe) and the existing 9.9c `upgrade_vault_v1_to_v2(path, password)→VaultUpgradeResult`. The CLI lives in a new `vault_upgrade_cli.py` module with no PySide6 import; the UI adds an action and slot to `MainWindow`. Vault stays locked after upgrade; no automatic flow.

**Tech Stack:** Python >=3.12,<3.14; PySide6>=6.7; cryptography>=42; argon2-cffi>=23; no new dependencies.

## Global Constraints

1. Python >=3.12,<3.14; PySide6>=6.7; no dependency/lockfile changes.
2. No automatic upgrade or startup probe.
3. No secrets in argv, logs, stdout, or error messages. CLI JSON includes hash metadata only.
4. No `--password`/`--master-password`/`-p` CLI arguments.
5. No `old_password`/`new_password` distinction — single password for v1 decrypt and v2 re-encrypt.
6. No `Change Password` action.
7. No `_vault_manager` — use `self.vault_manager`.
8. Protected: pyproject.toml (except `[project.scripts]`), poetry.lock, generated, vendor, build output.
9. No agent commit/push; final `READY_FOR_MANUAL_COMMIT` only.
10. `pytest` without `--timeout` flag or `pytest-timeout` plugin; use `-p no:cacheprovider`.

---

## File Map and Responsibilities

| File | Status | Responsibility |
|------|--------|---------------|
| `src/openadmindesk/core/vault_upgrade.py` | Modify | Add `inspect_vault_version(path: Path) -> int` |
| `src/openadmindesk/vault_upgrade_cli.py` | **Create** | Standalone CLI: argparse, password acquisition, text/JSON, exit codes |
| `src/openadmindesk/ui/main_window.py` | Modify | Add `upgrade_vault_action`, `_on_upgrade_vault()` slot |
| `pyproject.toml` | Modify | Add `[project.scripts]` entry |
| `tests/test_vault_upgrade.py` | Modify | Add probe tests |
| `tests/test_vault_upgrade_cli.py` | **Create** | CLI test suite + tomllib entry-point assertion |
| `tests/test_main_window.py` | Modify | Add upgrade slot tests |
| `docs/SECURITY_MODEL.md` | Modify | Document upgrade safety |
| `docs/VAULT_SPEC.md` | Modify | Mention upgrade surface |
| `docs/AUDIT_REMEDIATION_PLAN.md` | Modify | Mark 9.9d [x] |
| `docs/WORKLOG.md` | Modify | Append final evidence |

**Interfaces consumed/produced:**
- `inspect_vault_version(path: Path) -> int` — returns 1/2; raises `VaultUpgradeError`
- `upgrade_vault_v1_to_v2(path, master_password) -> VaultUpgradeResult` — existing 9.9c
- `VaultUpgradeResult` — source_version, target_version, accounts_reencrypted, source_sha256, target_sha256, backup_deleted, retained_backup_path
- `VaultUpgradeError(RuntimeError)` — message, rollback_succeeded, recovery_backup_path, source_sha256, backup_sha256
- `platform_utils.default_vault_path() -> str`, `self.vault_manager` (vault_path, is_unlocked, lock)

---

### Expected Final File List

```
 M src/openadmindesk/core/vault_upgrade.py
?? src/openadmindesk/vault_upgrade_cli.py
 M src/openadmindesk/ui/main_window.py
 M pyproject.toml
 M tests/test_vault_upgrade.py
?? tests/test_vault_upgrade_cli.py
 M tests/test_main_window.py
 M docs/SECURITY_MODEL.md
 M docs/VAULT_SPEC.md
 M docs/AUDIT_REMEDIATION_PLAN.md
 M docs/WORKLOG.md
?? docs/superpowers/specs/2026-07-15-vault-upgrade-ui-cli-design.md
?? docs/superpowers/plans/2026-07-15-vault-upgrade-ui-cli-implementation.md
```

**7 functional/test/config files + 4 docs + spec/plan. Never create `tests/test_pyproject_scripts.py`.**

---

## Task 1: Baseline Verification Only

**Files:** No modifications; verify current state only.

- [ ] **Step 1: Record `git status --short`**
- [ ] **Step 2: Record `git diff --stat`**
- [ ] **Step 3: Record `git diff --check`**
  Expected: only WORKLOG modified plus untracked spec and plan files; no whitespace errors.
- [ ] **Step 4: Run full headless baseline pytest**
  ```bash
  QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider
  ```
  Expected: Exit 0. Record actual count without hardcoding in expected.
- [ ] **Step 5: Run repository Ruff baseline**
  ```bash
  ruff check src tests
  ```
  Expected: Exit 0. No `--no-cache` flag, no Bandit baseline.

**Command record format for every task:**
```markdown
| Command | Exit | Outcome |
|---------|------|---------|
| `git status --short` | 0 | Only WORKLOG + untracked spec/plan files |
```

---

## Task 2: TDD Core `inspect_vault_version(Path) -> int`

**Files:** `tests/test_vault_upgrade.py` (modify — RED first), `src/openadmindesk/core/vault_upgrade.py` (modify — implement).

**Interfaces:** Consumes `detect_version`, `VaultFormat.validate_vault_format`, `VaultUpgradeError`. Produces `inspect_vault_version`.

- [ ] **Step 1: Add `inspect_vault_version` to existing import block in `test_vault_upgrade.py`**
  ```python
  from openadmindesk.core.vault_upgrade import (
      VaultUpgradeError,
      VaultUpgradeResult,
      inspect_vault_version,
      upgrade_vault_v1_to_v2,
  )
  ```
- [ ] **Step 2: Write failing test — v1 fixture returns 1**
  ```python
  class TestInspectVaultVersion:
      def test_inspect_v1_returns_1(self, tmp_path: Path) -> None:
          vault_file = tmp_path / "vault.json"
          _write_v1_vault(vault_file, "test_password")
          assert inspect_vault_version(vault_file) == 1
  ```
- [ ] **Step 3: Run to confirm RED**
  ```bash
  python3 -m pytest tests/test_vault_upgrade.py::TestInspectVaultVersion::test_inspect_v1_returns_1 -v --tb=short
  ```
  Expected: FAIL with `ImportError: cannot import name 'inspect_vault_version'`.
- [ ] **Step 4: Write failing test — v2 returns 2**
  ```python
      def test_inspect_v2_returns_2(self, tmp_path: Path) -> None:
          vault_file = tmp_path / "vault.json"
          from openadmindesk.core.vault_manager import VaultManager
          vm = VaultManager(str(vault_file))
          try:
              assert vm.setup_master_password("test_password")
          finally:
              vm.close()
          assert inspect_vault_version(vault_file) == 2
  ```
- [ ] **Step 5: Write failing test — non-regular paths raise `VaultUpgradeError`**
  ```python
      @pytest.mark.parametrize("case", ["missing", "directory", "symlink", "fifo"])
      def test_inspect_rejects_non_regular_paths(self, tmp_path: Path, case: str) -> None:
          if case == "missing":
              path = tmp_path / "missing.json"
          elif case == "directory":
              path = tmp_path
          elif case == "symlink":
              (tmp_path / "symlink.json").symlink_to("/nonexistent/file.json")
              path = tmp_path / "symlink.json"
          elif case == "fifo":
              fifo = tmp_path / "fifo"
              os.mkfifo(str(fifo))
              path = fifo
          with pytest.raises(VaultUpgradeError):
              inspect_vault_version(path)
  ```
- [ ] **Step 6: Write failing test — malformed JSON raises `VaultUpgradeError`**
  ```python
      def test_inspect_rejects_malformed_json(self, tmp_path: Path) -> None:
          path = tmp_path / "vault.json"
          path.write_text("{ invalid json }", encoding="utf-8")
          with pytest.raises(VaultUpgradeError):
              inspect_vault_version(path)
  ```
- [ ] **Step 7: Write failing test — non-dict JSON raises `VaultUpgradeError`**
  ```python
      def test_inspect_rejects_non_object(self, tmp_path: Path) -> None:
          path = tmp_path / "vault.json"
          path.write_text("[]", encoding="utf-8")
          with pytest.raises(VaultUpgradeError):
              inspect_vault_version(path)
  ```
- [ ] **Step 8: Write failing test — unknown version raises `VaultUpgradeError`**
  ```python
      def test_inspect_rejects_unknown_version(self, tmp_path: Path) -> None:
          path = tmp_path / "vault.json"
          path.write_text(json.dumps({"version": 99}), encoding="utf-8")
          with pytest.raises(VaultUpgradeError):
              inspect_vault_version(path)
  ```
- [ ] **Step 9: Write failing test — structurally invalid v1 raises `VaultUpgradeError`**
  ```python
      def test_inspect_rejects_structurally_invalid_v1(self, tmp_path: Path) -> None:
          path = tmp_path / "vault.json"
          path.write_text(json.dumps({"version": "1.0", "salt": "a" * 32}), encoding="utf-8")
          with pytest.raises(VaultUpgradeError):
              inspect_vault_version(path)
  ```
- [ ] **Step 10: Write failing test — no side effects (bytes, mode, mtime unchanged)**
  ```python
      def test_inspect_does_not_modify_file(self, tmp_path: Path) -> None:
          vault_file = tmp_path / "vault.json"
          _write_v1_vault(vault_file, "test_password")
          original_bytes = vault_file.read_bytes()
          original_mtime = vault_file.stat().st_mtime_ns
          original_mode = stat.S_IMODE(vault_file.stat().st_mode)
          result = inspect_vault_version(vault_file)
          assert result == 1
          assert vault_file.read_bytes() == original_bytes
          assert vault_file.stat().st_mtime_ns == original_mtime
          assert stat.S_IMODE(vault_file.stat().st_mode) == original_mode
  ```
- [ ] **Step 11: Run all new tests to confirm RED**
  ```bash
  python3 -m pytest tests/test_vault_upgrade.py::TestInspectVaultVersion -v --tb=short
  ```
- [ ] **Step 12: Implement `inspect_vault_version` in `vault_upgrade.py`**
  ```python
  def inspect_vault_version(path: Path) -> int:
      """Read-only probe of vault file format version.

      Returns 1 for v1 ("1.0"), 2 for v2 (integer 2).

      Raises VaultUpgradeError for inaccessible path, non-regular file,
      invalid UTF-8 JSON, non-dict content, unknown version, or format
      validation failure. Side-effect-free: does not modify file bytes,
      mtime, mode, or inode.
      """
      try:
          st = path.lstat()
      except OSError:
          raise VaultUpgradeError("Vault file is inaccessible") from None

      if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
          raise VaultUpgradeError("Vault file is not a regular file")

      try:
          text = path.read_text(encoding="utf-8")
          data: dict[str, object] = json.loads(text)
      except (OSError, UnicodeError, json.JSONDecodeError):
          raise VaultUpgradeError("Vault file is not valid UTF-8 JSON") from None

      if not isinstance(data, dict):
          raise VaultUpgradeError("Vault file is not a valid JSON object")

      version = detect_version(data)
      if version == 1:
          if not VaultFormat.validate_vault_format(data):
              raise VaultUpgradeError("Vault file format is invalid")
          return 1
      if version == 2:
          if not VaultFormat.validate_vault_format(data):
              raise VaultUpgradeError("Vault file format is invalid")
          return 2

      raise VaultUpgradeError("Vault file version is unsupported")
  ```
- [ ] **Step 13: Run tests to confirm GREEN**
  ```bash
  python3 -m pytest tests/test_vault_upgrade.py::TestInspectVaultVersion -v --tb=short
  ```
- [ ] **Step 14: Run py_compile + ruff on both files**
  ```bash
  python3 -m py_compile src/openadmindesk/core/vault_upgrade.py tests/test_vault_upgrade.py
  ruff check src/openadmindesk/core/vault_upgrade.py tests/test_vault_upgrade.py
  ```

---

## Task 3: TDD Standalone CLI

**Files:** Create `tests/test_vault_upgrade_cli.py` (RED first), create `src/openadmindesk/vault_upgrade_cli.py`.

**Interfaces:** Consumes `inspect_vault_version`, `upgrade_vault_v1_to_v2`, `VaultUpgradeError`,
`VaultUpgradeResult`, `platform_utils.default_vault_path`.
Produces `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Create test file with imports at module level so RED is clean ModuleNotFound**
  ```python
  """Tests for vault upgrade standalone CLI."""
  from __future__ import annotations

  import json
  import os
  import subprocess
  import sys
  from pathlib import Path

  import pytest

  import openadmindesk.vault_upgrade_cli as cli
  ```
  Expected RED: `ModuleNotFoundError: No module named 'openadmindesk.vault_upgrade_cli'`.

- [ ] **Step 2: Write failing tests — all tests import `cli` at module level, monkeypatch `cli` object (not string paths)**
  ```python
  class TestCliAlreadyV2:
      """When probe returns 2, CLI exits 0 and says already current."""

      def test_text_v2(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """v2 text output says vault is already current. Password never needed."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 2)
          monkeypatch.setattr(cli, "_acquire_password",
                              lambda *a, **kw: (_ for _ in ()).throw(
                                  AssertionError("_acquire_password must not be called on v2 path")))
          ec = cli.main(["--vault", str(f)])
          out = capsys.readouterr().out
          assert ec == 0
          assert out.strip() == "Vault is already using the latest format (v2)."

      def test_json_v2(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """v2 JSON output has exact six-key shape."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 2)
          ec = cli.main(["--vault", str(f), "--format", "json"])
          d = json.loads(capsys.readouterr().out)
          assert ec == 0
          assert d == {"status": "already_current", "source_version": 2, "target_version": 2}

  class TestCliV1Flow:
      """V1 vault requires --confirm-upgrade, then password, then core call."""

      def test_no_confirm_stderr(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Missing --confirm-upgrade prints to stderr and exits 2."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          ec = cli.main(["--vault", str(f)])
          err = capsys.readouterr().err
          assert ec == 2
          assert "confirm-upgrade" in err.lower()

      def test_no_confirm_proves_password_untouched(self, tmp_path, capsys, monkeypatch) -> None:
          """Without --confirm-upgrade, password code is never reached."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setattr(cli.os.environ, "get", lambda k, d="": (_ for _ in ()).throw(RuntimeError("must not call")))
          ec = cli.main(["--vault", str(f)])
          err = capsys.readouterr().err
          assert ec == 2
          assert "confirm-upgrade" in err.lower()

      def test_env_text_success(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Env password + --confirm-upgrade prints exact success, no secrets."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "test-pw")
          monkeypatch.setattr(cli, "upgrade_vault_v1_to_v2",
                              lambda p, pw: cli.VaultUpgradeResult(
                                  1, 2, 3, "a" * 64, "b" * 64, True, None))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          out = capsys.readouterr().out
          assert ec == 0
          assert "Vault upgraded from v1 to v2. Accounts re-encrypted: 3" in out
          assert "Backup retained:" not in out
          assert "test-pw" not in out
          assert "aaaa" not in out

      def test_env_json_exact(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """JSON output matches exact eight-field shape."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "test-pw")
          monkeypatch.setattr(cli, "upgrade_vault_v1_to_v2",
                              lambda p, pw: cli.VaultUpgradeResult(
                                  1, 2, 2, "c" * 64, "d" * 64, False,
                                  str(tmp_path / "backup.json")))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade", "--format", "json"])
          d = json.loads(capsys.readouterr().out)
          assert ec == 0
          assert d["status"] == "upgraded"
          assert d["source_version"] == 1
          assert d["target_version"] == 2
          assert d["accounts_reencrypted"] == 2
          assert d["backup_deleted"] is False
          assert d["retained_backup_path"] is not None
          assert "test-pw" not in json.dumps(d)

      def test_custom_env_captures_args(self, tmp_path: Path, monkeypatch) -> None:
          """Custom --password-env reads correct var, sends correct Path+password."""
          sent: list[tuple[str, str]] = []
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("MY_CUSTOM", "custom-pw")
          monkeypatch.setattr(cli, "upgrade_vault_v1_to_v2",
                              lambda p, pw: sent.append((str(p), pw)) or
                              cli.VaultUpgradeResult(1, 2, 1, "x" * 64, "y" * 64, True, None))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade",
                         "--password-env", "MY_CUSTOM"])
          assert ec == 0
          assert len(sent) == 1
          assert sent[0][0] == str(f)
          assert sent[0][1] == "custom-pw"

      def test_tty_getpass_captures_args(self, tmp_path: Path, monkeypatch) -> None:
          """TTY getpass sends the prompted password to core."""
          sent: list[tuple[str, str]] = []
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
          monkeypatch.setattr(cli.getpass, "getpass", lambda p="": "tty-pw")
          monkeypatch.setattr(cli, "upgrade_vault_v1_to_v2",
                              lambda p, pw: sent.append((str(p), pw)) or
                              cli.VaultUpgradeResult(1, 2, 1, "m" * 64, "n" * 64, True, None))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          assert ec == 0
          assert len(sent) == 1
          assert sent[0][0] == str(f)
          assert sent[0][1] == "tty-pw"

      def test_empty_getpass_exit_2(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Empty getpass returns exit 2."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
          monkeypatch.setattr(cli.getpass, "getpass", lambda p="": "")
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          err = capsys.readouterr().err
          assert ec == 2
          assert "password" in err.lower()

      def test_non_tty_no_env_exit_2(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """No TTY and no env var returns exit 2."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
          monkeypatch.delenv("OPENADMINDESK_VAULT_PASSWORD", raising=False)
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          err = capsys.readouterr().err
          assert ec == 2
          assert "password" in err.lower()
  ```
- [ ] **Step 3: Write remaining error and No-Qt tests**
  ```python
  class TestCliError:
      """VaultUpgradeError and generic exception handling."""

      def test_wrong_password_text(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Text error output has 'Error:' prefix, no secret in output."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "wrong")
          monkeypatch.setattr(
              cli, "upgrade_vault_v1_to_v2",
              lambda p, pw: (_ for _ in ()).throw(
                  cli.VaultUpgradeError("Invalid source password")))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          err = capsys.readouterr().err
          assert ec == 1
          assert "Error:" in err
          assert "wrong" not in err.lower()

      def test_error_json_six_fields(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """JSON error output has exactly six keys, no secret."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "wrong")
          monkeypatch.setattr(
              cli, "upgrade_vault_v1_to_v2",
              lambda p, pw: (_ for _ in ()).throw(
                  cli.VaultUpgradeError(
                      "Invalid", rollback_succeeded=None,
                      source_sha256="a" * 64)))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade", "--format", "json"])
          d = json.loads(capsys.readouterr().out)
          assert ec == 1
          assert d["status"] == "error"
          assert d["rollback_succeeded"] is None
          for k in ("status", "error", "rollback_succeeded",
                     "recovery_backup_path", "source_sha256", "backup_sha256"):
              assert k in d

      def test_error_json_rollback_true(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """VaultUpgradeError with rollback_succeeded=True includes metadata."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "x")
          monkeypatch.setattr(
              cli, "upgrade_vault_v1_to_v2",
              lambda p, pw: (_ for _ in ()).throw(
                  cli.VaultUpgradeError(
                      "Failed", rollback_succeeded=True,
                      recovery_backup_path="/tmp/bak.json",
                      source_sha256="s" * 64, backup_sha256="b" * 64)))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade", "--format", "json"])
          d = json.loads(capsys.readouterr().out)
          assert ec == 1
          assert d["status"] == "error"
          assert d["rollback_succeeded"] is True

      def test_generic_exception_text(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Non-VaultUpgradeError prints safe generic message, no raw exception."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "x")
          monkeypatch.setattr(
              cli, "upgrade_vault_v1_to_v2",
              lambda p, pw: (_ for _ in ()).throw(RuntimeError("boom")))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade"])
          err = capsys.readouterr().err
          assert ec == 1
          assert "Unexpected error" in err
          assert "boom" not in err

      def test_generic_exception_json(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Generic exception JSON is safe, six keys, no raw exception."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "x")
          monkeypatch.setattr(
              cli, "upgrade_vault_v1_to_v2",
              lambda p, pw: (_ for _ in ()).throw(RuntimeError("boom")))
          ec = cli.main(["--vault", str(f), "--confirm-upgrade", "--format", "json"])
          d = json.loads(capsys.readouterr().out)
          assert ec == 1
          assert d["status"] == "error"
          assert d["rollback_succeeded"] is None
          assert d["source_sha256"] is None
          assert d["error"] == "Unexpected error during vault upgrade"
          assert "boom" not in json.dumps(d)

      def test_missing_vault(self, capsys, monkeypatch) -> None:
          """Missing vault shows Error: prefix."""
          monkeypatch.setattr(cli, "default_vault_path", lambda: "/nonexistent/v.json")
          ec = cli.main([])
          err = capsys.readouterr().err
          assert ec == 1
          assert "Error:" in err

      def test_custom_env_missing_source(self, tmp_path: Path, capsys, monkeypatch) -> None:
          """Custom --password-env mentions the custom var name, not default."""
          f = tmp_path / "vault.json"
          f.write_text("{}", encoding="utf-8")
          monkeypatch.setattr(cli, "inspect_vault_version", lambda p: 1)
          monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
          ec = cli.main(["--vault", str(f), "--confirm-upgrade",
                         "--password-env", "MY_CUSTOM_ENV"])
          err = capsys.readouterr().err
          assert ec == 2
          assert "MY_CUSTOM_ENV" in err
          assert "OPENADMINDESK_VAULT_PASSWORD" not in err

      def test_unknown_option_exits_2(self, capsys) -> None:
          """Unknown option exits 2 with usage/error to stderr (argparse)."""
          with pytest.raises(SystemExit) as exc:
              cli.main(["--unknown-option"])
          assert exc.value.code == 2
          err = capsys.readouterr().err
          assert "usage:" in err or "error:" in err

  class TestCliNoQt:
      def test_no_pyside6_import(self) -> None:
          """Subprocess imports CLI module and asserts PySide6 not loaded."""
          script = (
              "import json\n"
              "import sys\n"
              "from openadmindesk.vault_upgrade_cli import main\n"
              "p = [m for m in sys.modules if 'PySide6' in m]\n"
              "print(json.dumps(p))\n"
          )
          repo_root = str(Path(__file__).resolve().parent.parent)
          env = {**os.environ, "PYTHONPATH": repo_root + "/src",
                 "PYTHONDONTWRITEBYTECODE": "1"}
          r = subprocess.run(
              [sys.executable, "-c", script],
              capture_output=True, text=True, env=env)
          assert r.returncode == 0, r.stderr
          assert json.loads(r.stdout.strip()) == [], f"PySide6 loaded: {r.stdout}"
  ```
- [ ] **Step 4: Run all CLI tests to confirm RED**
  ```bash
  python3 -m pytest tests/test_vault_upgrade_cli.py -v --tb=short
  ```
  Expected: All FAIL with `ModuleNotFoundError: No module named 'openadmindesk.vault_upgrade_cli'`.
- [ ] **Step 5: Implement `src/openadmindesk/vault_upgrade_cli.py`**
  ```python
  """Standalone CLI for vault upgrade. No PySide6 import.

  Usage: openadmindesk-vault-upgrade [--vault PATH] [--confirm-upgrade]
                                     [--password-env VAR] [--format text|json]

  No secrets accepted via argv. Password from env or TTY getpass only.
  """
  from __future__ import annotations

  import argparse
  import getpass
  import json
  import os
  import sys
  from pathlib import Path

  from openadmindesk.core.vault_upgrade import (
      VaultUpgradeError,
      VaultUpgradeResult,
      inspect_vault_version,
      upgrade_vault_v1_to_v2,
  )
  from openadmindesk.platform.platform_utils import default_vault_path


  def _build_parser() -> argparse.ArgumentParser:
      p = argparse.ArgumentParser(
          prog="openadmindesk-vault-upgrade",
          description="Upgrade vault from v1 (PBKDF2) to v2 (Argon2id).")
      p.add_argument("--vault", default=None,
                     help="Vault JSON path (default: platform default)")
      p.add_argument("--password-env",
                     default="OPENADMINDESK_VAULT_PASSWORD",
                     help="Env var for password")
      p.add_argument("--confirm-upgrade", action="store_true",
                     help="Acknowledge v1 to v2 upgrade")
      p.add_argument("--format", choices=("text", "json"), default="text",
                     help="Output format")
      return p


  def _acquire_password(args: argparse.Namespace) -> str | None:
      pw = os.environ.get(args.password_env, "")
      if pw:
          return pw
      if sys.stdin.isatty():
          pw = getpass.getpass("Master password: ")
          if pw:
              return pw
      return None


  def main(argv: list[str] | None = None) -> int:
      args = _build_parser().parse_args(argv)
      vp = Path(args.vault) if args.vault else Path(default_vault_path())
      if not vp.exists() or not vp.is_file():
            _emit_error(f"Vault file not found: {vp}", None, args.format)
            return 1
      try:
        ver = inspect_vault_version(vp)
    except VaultUpgradeError as e:
        _emit_error(str(e), e, args.format)
        return 1
    except Exception:
        _emit_error("Unexpected error during vault upgrade", None, args.format)
        return 1
      if ver == 2:
          _emit_already_current(args.format)
          return 0
      if not args.confirm_upgrade:
          m = "--confirm-upgrade is required for v1 to v2 upgrade"
          _emit_error(m, None, args.format)
          return 2
      pw = _acquire_password(args)
      if pw is None:
          m = (
              f"No password. Set {args.password_env} or run on TTY."
          )
          _emit_error(m, None, args.format)
          return 2
      try:
          r = upgrade_vault_v1_to_v2(vp, pw)
      except VaultUpgradeError as e:
          _emit_error(str(e), e, args.format)
          return 1
      except Exception:
          _emit_error("Unexpected error during vault upgrade", None, args.format)
          return 1
      _emit_result(r, args.format)
      return 0


  def _emit_already_current(fmt: str) -> None:
      if fmt == "json":
          print(json.dumps({"status": "already_current",
                            "source_version": 2, "target_version": 2}))
      else:
            print("Vault is already using the latest format (v2).")


  def _emit_text_error(msg: str, e: VaultUpgradeError | None) -> None:
      lines = [f"Error: {msg}"]
      if e is not None:
          if e.rollback_succeeded is True:
              lines.append("Original v1 restored.")
          elif e.rollback_succeeded is False:
              lines.append("Rollback failed.")
          if e.recovery_backup_path:
              lines.append(f"Recovery: {e.recovery_backup_path}")
      print("\n".join(lines), file=sys.stderr)


  def _emit_json_error(msg: str, e: VaultUpgradeError | None) -> None:
      if e is not None:
          d = {
              "status": "error",
              "error": msg,
              "rollback_succeeded": e.rollback_succeeded,
              "recovery_backup_path": e.recovery_backup_path,
              "source_sha256": e.source_sha256,
              "backup_sha256": e.backup_sha256,
          }
      else:
          d = {
              "status": "error",
              "error": msg,
              "rollback_succeeded": None,
              "recovery_backup_path": None,
              "source_sha256": None,
              "backup_sha256": None,
          }
      print(json.dumps(d))


  def _emit_error(msg: str, e: VaultUpgradeError | None, fmt: str) -> None:
      if fmt == "json":
          _emit_json_error(msg, e)
      else:
          _emit_text_error(msg, e)


  def _emit_result(r: VaultUpgradeResult, fmt: str) -> None:
      if fmt == "json":
          print(json.dumps({
              "status": "upgraded",
              "source_version": r.source_version,
              "target_version": r.target_version,
              "accounts_reencrypted": r.accounts_reencrypted,
              "source_sha256": r.source_sha256,
              "target_sha256": r.target_sha256,
              "backup_deleted": r.backup_deleted,
              "retained_backup_path": r.retained_backup_path,
          }))
      else:
            print(f"Vault upgraded from v{r.source_version} to "
                  f"v{r.target_version}. Accounts re-encrypted: "
                  f"{r.accounts_reencrypted}")
            if not r.backup_deleted and r.retained_backup_path:
                print(f"Backup retained: {r.retained_backup_path}")


  if __name__ == "__main__":
      sys.exit(main())
  ```
- [ ] **Step 5: Run tests GREEN**
  ```bash
  python3 -m pytest tests/test_vault_upgrade_cli.py -v --tb=short
  ```
  No skip accepted for `test_no_pyside6_import` — subprocess approach avoids pre-load.
- [ ] **Step 6: py_compile + ruff**
  ```bash
  python3 -m py_compile src/openadmindesk/vault_upgrade_cli.py tests/test_vault_upgrade_cli.py
  ruff check src/openadmindesk/vault_upgrade_cli.py tests/test_vault_upgrade_cli.py
  ```

---

## Task 4: TDD UI Integration

**Files:** `tests/test_main_window.py` (modify — RED first), `src/openadmindesk/ui/main_window.py`
(modify — implement).

**Interfaces:** Consumes `self.vault_manager` (vault_path, is_unlocked, lock),
`self._last_vault_unlocked`, `self._update_vault_menu()`, `inspect_vault_version`,
`upgrade_vault_v1_to_v2`, `VaultUpgradeError`, `VaultUpgradeResult`. Uses
`QMessageBox.warning` for upgrade prompt and `QMessageBox.question` for relock.

- [ ] **Step 1: Import types + define local dialog mock helper (`_DlgMocks`)**
  ```python
  from pathlib import Path
  from PySide6.QtWidgets import QInputDialog, QMessageBox
  from openadmindesk.core.vault_upgrade import (
      VaultUpgradeError,
      VaultUpgradeResult,
      inspect_vault_version,
      upgrade_vault_v1_to_v2,
  )

  class _DlgMocks:
      """Monkeypatches QMessageBox methods; uses monkeypatch directly (no window param).
      warning patched separately from question. Default: warning->Yes, question->No.
      Captures all calls in lists for assertion.
      """
      def __init__(self, monkeypatch) -> None:
          self.infos: list[str] = []
          self.warnings: list[str] = []
          self.criticals: list[str] = []
          self.questions: list[str] = []
          monkeypatch.setattr(
              QMessageBox, "information",
              lambda *a, **kw: self.infos.append(str(a[2])))
          monkeypatch.setattr(
              QMessageBox, "critical",
              lambda *a, **kw: self.criticals.append(str(a[2])))
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (self.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (self.questions.append(str(a[2])),
                                QMessageBox.No)[1])
  ```
- [ ] **Step 2: Write all failing tests**
  ```python
  class TestUpgradeVaultSlot:
      """Tests for _on_upgrade_vault slot. No modal dialogs — all mocked."""

      def _prepare(
          self, monkeypatch, window, *,
          version: int = 1,
          probe_raises: type[Exception] | None = None,
          is_unlocked: bool = False,
          vault_path: str = "/tmp/test_vault.json",
          upgrade_result=None,
          upgrade_error=None,
          qinput_result=("pw", True),
      ) -> dict:
          """Configure fakes and return context dict with 'calls', 'state', 'lock_calls'.
          Patches is_unlocked to read state['unlocked']; lock appends and sets state False.
          Fake upgrade always records (Path, password) then returns result or raises error.
          Never returns None — default valid VaultUpgradeResult when no result/error given.
          Uses monkeypatch directly.
          """
          monkeypatch.setattr(
              window.vault_manager, "vault_path", vault_path)
          if probe_raises:
              monkeypatch.setattr(
                  "openadmindesk.ui.main_window.inspect_vault_version",
                  lambda p: (_ for _ in ()).throw(probe_raises("bad vault")))
          else:
              monkeypatch.setattr(
                  "openadmindesk.ui.main_window.inspect_vault_version",
                  lambda p: version)
          ctx: dict = {
              "calls": [],
              "state": {"unlocked": is_unlocked},
              "lock_calls": [],
          }
          monkeypatch.setattr(
              window.vault_manager, "is_unlocked",
              lambda: ctx["state"]["unlocked"])

          def _lock() -> None:
              ctx["lock_calls"].append(True)
              ctx["state"]["unlocked"] = False
          monkeypatch.setattr(
              window.vault_manager, "lock", _lock)
          monkeypatch.setattr(
              QInputDialog, "getText",
              lambda *a, **kw: qinput_result)

          def _fake_upgrade(p: Path, pw: str) -> VaultUpgradeResult:
              ctx["calls"].append((p, pw))
              if upgrade_error is not None:
                  raise upgrade_error
              if upgrade_result is not None:
                  return upgrade_result
              return VaultUpgradeResult(1, 2, 0, "x" * 64, "y" * 64, True, None)
          monkeypatch.setattr(
              "openadmindesk.ui.main_window.upgrade_vault_v1_to_v2",
              _fake_upgrade)
          return ctx

      # ── Menu action wiring ────────────────────────────────────────────
      def test_upgrade_action_wired(self) -> None:
          """Upgrade Vault Security action exists and connects to slot."""
          w = MainWindow()
          assert hasattr(w, "upgrade_vault_action")
          assert w.upgrade_vault_action.text() == "Upgrade Vault Security\u2026"

      def test_upgrade_action_trigger(self, monkeypatch) -> None:
          """Triggering action shows v2 info via real slot path; no modal."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              "openadmindesk.ui.main_window.inspect_vault_version",
              lambda p: 2)
          w.upgrade_vault_action.triggered.emit()
          assert len(dm.infos) == 1
          assert "v2" in dm.infos[0].lower()

      # ── Probe errors and v2 ────────────────────────────────────────────
      def test_probe_error_critical(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          self._prepare(monkeypatch, w,
                        probe_raises=VaultUpgradeError)
          w._on_upgrade_vault()
          assert len(dm.criticals) == 1

      def test_v2_info(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          self._prepare(monkeypatch, w, version=2)
          w._on_upgrade_vault()
          assert len(dm.infos) == 1
          assert "v2" in dm.infos[0].lower()

      # ── Warning cancel ────────────────────────────────────────────────
      def test_warning_cancel_no_core(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.No)[1])
          ctx = self._prepare(monkeypatch, w)
          w._on_upgrade_vault()
          assert len(dm.warnings) == 1  # stopped at first warning
          assert len(ctx["calls"]) == 0
          assert len(ctx["lock_calls"]) == 0

      # ── Relock question cancel keeps state true ───────────────────────
      def test_relock_question_cancel_stays_true(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          # question stays No (default)
          ctx = self._prepare(monkeypatch, w, is_unlocked=True)
          w._last_vault_unlocked = True
          w._on_upgrade_vault()
          assert len(dm.warnings) == 1  # initial upgrade warning
          assert len(dm.questions) == 1  # relock question shown
          assert ctx["state"]["unlocked"] is True
          assert len(ctx["lock_calls"]) == 0
          assert len(ctx["calls"]) == 0

      # ── Relock consent, then password cancel/empty ─────────────────────
      def test_relock_consent_password_cancel_no_call(self, monkeypatch) -> None:
          """Password dialog cancelled (ok=False) locks vault but makes no core call."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          ctx = self._prepare(monkeypatch, w, is_unlocked=True,
                              qinput_result=("", False))
          w._last_vault_unlocked = True
          w._on_upgrade_vault()
          assert ctx["state"]["unlocked"] is False
          assert len(ctx["lock_calls"]) == 1
          assert len(ctx["calls"]) == 0

      def test_relock_consent_password_empty_no_call(self, monkeypatch) -> None:
          """Password dialog ok but empty (ok=True, pw='') locks vault but makes no core call."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          ctx = self._prepare(monkeypatch, w, is_unlocked=True,
                              qinput_result=("", True))
          w._last_vault_unlocked = True
          w._on_upgrade_vault()
          assert ctx["state"]["unlocked"] is False
          assert len(ctx["lock_calls"]) == 1
          assert len(ctx["calls"]) == 0

      # ── Full flow: exact Path and password once ────────────────────────
      def test_full_flow_exact_args_once(self, monkeypatch) -> None:
          """Full flow: exact Path and password delivered once to core."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          vault_path = "/tmp/test_vault.json"
          ctx = self._prepare(monkeypatch, w, is_unlocked=True,
                              vault_path=vault_path,
                              qinput_result=("secret123", True))
          w._on_upgrade_vault()
          assert len(ctx["calls"]) == 1
          assert ctx["calls"][0][0] == vault_path
          assert ctx["calls"][0][1] == "secret123"

      # ── Lock/menu sync and no auto-lock message ────────────────────────
      def test_full_flow_lock_sync(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          ctx = self._prepare(monkeypatch, w, is_unlocked=True,
                              upgrade_result=VaultUpgradeResult(
                                  1, 2, 0, "a" * 64, "b" * 64, True, None))
          w._last_vault_unlocked = True
          w._on_upgrade_vault()
          assert ctx["state"]["unlocked"] is False
          assert w._last_vault_unlocked is False
          assert w.lock_vault_action.isEnabled() is False
          assert w.unlock_vault_action.isEnabled() is True

      def test_no_auto_lock_message_after_upgrade(self, monkeypatch) -> None:
          """After upgrade locks vault, subsequent poll does not emit auto-lock."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          show_messages: list[str] = []
          monkeypatch.setattr(
              w.connection_event_area, "showMessage",
              lambda msg, *a, **kw: show_messages.append(str(msg)))
          self._prepare(monkeypatch, w, is_unlocked=True,
                        upgrade_result=VaultUpgradeResult(
                            1, 2, 0, "a" * 64, "b" * 64, True, None))
          w._on_upgrade_vault()
          w._poll_vault_lock_state()
          assert not any("auto-locked" in m.lower() for m in show_messages)

      # ── Backup scenarios ──────────────────────────────────────────────
      def test_backup_deleted_info(self, monkeypatch) -> None:
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w,
                        upgrade_result=VaultUpgradeResult(
                            1, 2, 3, "c" * 64, "d" * 64, True, None))
          w._on_upgrade_vault()
          assert len(dm.infos) == 1
          assert "Backup removed" in dm.infos[0]

      def test_backup_retained_warning(self, monkeypatch) -> None:
          """Retained backup yields two warnings: upgrade prompt + backup warning."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w,
                        upgrade_result=VaultUpgradeResult(
                            1, 2, 2, "e" * 64, "f" * 64,
                            False, "/tmp/bak.json"))
          w._on_upgrade_vault()
          assert len(dm.warnings) == 2
          assert "backup" in dm.warnings[1].lower()

      # ── Rollback scenarios ────────────────────────────────────────────
      def test_error_rollback_none_critical(self, monkeypatch) -> None:
          """rollback_succeeded=None -> critical, source not replaced."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w,
                        upgrade_error=VaultUpgradeError(
                            "Invalid", rollback_succeeded=None))
          w._on_upgrade_vault()
          assert len(dm.criticals) == 1
          assert "not replaced" in dm.criticals[0].lower()

      def test_error_rollback_true_warning(self, monkeypatch) -> None:
          """rollback_succeeded=True -> warning, original restored."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w,
                        upgrade_error=VaultUpgradeError(
                            "Failed", rollback_succeeded=True,
                            recovery_backup_path="/tmp/bak.json"))
          w._on_upgrade_vault()
          assert len(dm.warnings) == 2
          assert "Original v1 restored" in dm.warnings[1]
          assert "bak.json" in dm.warnings[1]

      def test_error_rollback_false_critical(self, monkeypatch) -> None:
          """rollback_succeeded=False -> critical, rollback failed."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w,
                        upgrade_error=VaultUpgradeError(
                            "Disaster", rollback_succeeded=False,
                            recovery_backup_path="/tmp/bak.json"))
          w._on_upgrade_vault()
          assert len(dm.criticals) == 1
          assert "Rollback failed" in dm.criticals[0]

      # ── No hashes or password in UI ────────────────────────────────────
      def test_no_secrets_in_ui_messages(self, monkeypatch) -> None:
          """No hex hash or entered password leaks into QMessageBox text."""
          w = MainWindow()
          dm = _DlgMocks(monkeypatch)
          monkeypatch.setattr(
              QMessageBox, "warning",
              lambda *a, **kw: (dm.warnings.append(str(a[2])),
                                QMessageBox.Yes)[1])
          monkeypatch.setattr(
              QMessageBox, "question",
              lambda *a, **kw: (dm.questions.append(str(a[2])),
                                QMessageBox.Yes)[1])
          self._prepare(monkeypatch, w, is_unlocked=True,
                        qinput_result=("visible-secret-test-value", True),
                        upgrade_result=VaultUpgradeResult(
                            1, 2, 1, "abcdef1234567890" * 4,
                            "deadbeefcafebabe" * 4, False, "/tmp/bak.json"))
          w._on_upgrade_vault()
          joined = " ".join(dm.warnings + dm.infos +
                            dm.criticals + dm.questions)
          assert "abcdef" not in joined
          assert "deadbeef" not in joined
          assert "visible-secret-test-value" not in joined
  ```
- [ ] **Step 3: Run tests to confirm RED**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window.py -v --tb=short -p no:cacheprovider -k upgrade
  ```
  Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute '_on_upgrade_vault'`.
- [ ] **Step 4: Implement `_on_upgrade_vault` + `_show_upgrade_error` in `main_window.py`**
  Add import:
  ```python
  from pathlib import Path
  from openadmindesk.core.vault_upgrade import (
      VaultUpgradeError,
      inspect_vault_version,
      upgrade_vault_v1_to_v2,
  )
  ```
  Ensure only action is inserted before EXISTING separator, no new separator added:
  ```python
          self.upgrade_vault_action = QAction(
              _("Upgrade Vault Security\u2026"), self)
          self.upgrade_vault_action.triggered.connect(self._on_upgrade_vault)
          vault_menu.addAction(self.upgrade_vault_action)
  ```
  Add methods (one coherent handler, no thought text):
  ```python
      def _on_upgrade_vault(self) -> None:
          vp = Path(self.vault_manager.vault_path)
          try:
              v = inspect_vault_version(vp)
          except VaultUpgradeError as e:
              QMessageBox.critical(
                  self, "Vault Upgrade",
                  f"Could not read vault file:\n{e}")
              return
          if v == 2:
              QMessageBox.information(
                  self, "Vault Upgrade", "Already using v2.")
              return
          warning_text = (
              "Upgrade vault from v1 (PBKDF2) to v2 (Argon2id)?\n\n"
              "A backup will be created before upgrade.\n"
              "Ensure no other OpenAdminDesk instance is writing to the vault."
          )
          if QMessageBox.warning(
              self, "Vault Upgrade", warning_text,
              QMessageBox.Yes | QMessageBox.No
          ) != QMessageBox.Yes:
              return
          if self.vault_manager.is_unlocked():
              if QMessageBox.question(
                  self, "Vault Upgrade",
                  "Vault will be locked. Re-enter password? Continue?",
                  QMessageBox.Yes | QMessageBox.No
              ) != QMessageBox.Yes:
                  return
              self.vault_manager.lock()
              self._last_vault_unlocked = False
              self._update_vault_menu()
          pw, ok = QInputDialog.getText(
              self, "Vault Upgrade", "Master password:",
              QLineEdit.Password)
          if not ok or not pw:
              return
          try:
              r = upgrade_vault_v1_to_v2(vp, pw)
          except VaultUpgradeError as e:
              self._show_upgrade_error(e)
              return
          if r.backup_deleted:
              QMessageBox.information(
                  self, "Vault Upgrade",
                  "Upgraded to v2. Backup removed.")
          else:
              m = "Upgraded to v2."
              if r.retained_backup_path:
                  m += f"\nBackup retained: {r.retained_backup_path}"
              QMessageBox.warning(self, "Vault Upgrade", m)

      def _show_upgrade_error(self, e: VaultUpgradeError) -> None:
          if e.rollback_succeeded is None:
              m = str(e) + "\n\nSource was not replaced."
              if e.recovery_backup_path:
                  m += f"\nRecovery: {e.recovery_backup_path}"
              QMessageBox.critical(self, "Vault Upgrade", m)
          elif e.rollback_succeeded is True:
              m = "Original v1 restored."
              if e.recovery_backup_path:
                  m += f"\nRecovery: {e.recovery_backup_path}"
              QMessageBox.warning(self, "Vault Upgrade", m)
          else:
              m = "Rollback failed."
              if e.recovery_backup_path:
                  m += f"\nRecovery: {e.recovery_backup_path}"
              QMessageBox.critical(self, "Vault Upgrade", m)
  ```
- [ ] **Step 5: Run tests GREEN**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window.py -v --tb=short -p no:cacheprovider -k upgrade
  ```
- [ ] **Step 6: Run full headless main_window tests**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window.py -q --tb=short -p no:cacheprovider
  ```
- [ ] **Step 7: py_compile + ruff**
  ```bash
  python3 -m py_compile src/openadmindesk/ui/main_window.py
  ruff check src/openadmindesk/ui/main_window.py
  ```

---

## Task 5: TDD Packaging Entrypoint

**Files:** `tests/test_vault_upgrade_cli.py` (modify — append assertion), `pyproject.toml` (modify — add script entry).

**No new test file created.** Appended to existing CLI test file.

- [ ] **Step 1: Append tomllib mapping assertion to `tests/test_vault_upgrade_cli.py`**
  ```python
  # ── pyproject.toml entry point assertion ────────────────────────────────
  def test_pyproject_has_vault_upgrade_script() -> None:
      import tomllib
      pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
      with pyproject.open("rb") as f:
          data = tomllib.load(f)
      scripts = data.get("project", {}).get("scripts", {})
      assert "openadmindesk-vault-upgrade" in scripts
      assert scripts["openadmindesk-vault-upgrade"] == "openadmindesk.vault_upgrade_cli:main"
  ```
- [ ] **Step 2: Run test to confirm RED**
  ```bash
  python3 -m pytest tests/test_vault_upgrade_cli.py::test_pyproject_has_vault_upgrade_script -v --tb=short
  ```
  Expected: FAIL: `AssertionError: assert 'openadmindesk-vault-upgrade' in {}`.
- [ ] **Step 3: Add console script to `pyproject.toml`**
  ```toml
  [project.scripts]
  openadmindesk = "openadmindesk.app:main"
  openadmindesk-vault-upgrade = "openadmindesk.vault_upgrade_cli:main"
  ```
- [ ] **Step 4: Run test GREEN**
  ```bash
  python3 -m pytest tests/test_vault_upgrade_cli.py::test_pyproject_has_vault_upgrade_script -v --tb=short
  ```

---

## Task 6: Independent Semantic / Security Review (Read-Only)

**Files:** All changed files across Tasks 1-5. **No edits during this task.**

- [ ] **Step 1: Prepare review dossier** (git status, diff, spec, acceptance criteria)
- [ ] **Step 2: Reviewer inspects against 10 criteria:**
  1. No secrets in argv, logs, stdout, error messages.
  2. `inspect_vault_version` is read-only (no file mutation).
  3. CLI exit codes match spec (0, 1, 2).
  4. UI mockable and headless-safe (QMessageBox/QInputDialog monkeypatched).
  5. No PySide6 import in `vault_upgrade_cli.py`.
  6. `pyproject.toml` has correct script entry.
  7. No `--password`/`-p`/`--master-password` CLI arg.
  8. No old/new password distinction.
  9. Vault stays locked after upgrade.
  10. No `_vault_manager` — uses `self.vault_manager`.
- [ ] **Step 3: Report verdict** — PASS or list each CRITICAL/HIGH/MEDIUM finding with exact file/line. No style or speculative findings.
- [ ] **Step 4: If PASS → proceed to Task 8 (skip Task 7).**

---

## Task 7: Conditional Targeted Corrections Only (TDD Per Finding)

**Files:** Only files identified with CRITICAL/HIGH/MEDIUM findings from Task 6.
**No review mixed in. Each finding gets its own RED→GREEN cycle.**

- [ ] **Step 1: For each independently confirmed behavioral defect, first add a focused
        failing regression test (RED) covering the exact defect.**
- [ ] **Step 2: Apply the minimal production fix to make the new test pass.
        Do not combine multiple fixes into one edit.**
- [ ] **Step 3: Run the minimal test subset that covers the corrected code (GREEN).**
- [ ] **Step 4: Max 2 correction cycles per finding. If unresolved after 2 cycles,
        document blocker and proceed.**
- [ ] **Step 5: If no findings → skip task entirely and proceed to Task 8.**

---

## Task 8: Second Reviewer Only (Final PASS Required)

**Files:** All changed files. **No edits.**

- [ ] **Step 1: Prepare final review dossier** (complete `git diff`, Task 6 verdict, any Task 7 corrections).
- [ ] **Step 2: Reviewer re-inspects same 10 criteria from Task 6.**
- [ ] **Step 3: Must return PASS.** If not PASS → return to Task 7 with exact findings.

---

## Task 9: Runtime Verification

**Files:** All changed Python files (6 total: vault_upgrade.py, vault_upgrade_cli.py, main_window.py, test_vault_upgrade.py, test_vault_upgrade_cli.py, test_main_window.py).

**No `test_pyproject_scripts.py` — it does not exist.**

- [ ] **Step 1: py_compile all 6 changed Python/test files**
  ```bash
  python3 -m py_compile \
    src/openadmindesk/core/vault_upgrade.py \
    src/openadmindesk/vault_upgrade_cli.py \
    src/openadmindesk/ui/main_window.py \
    tests/test_vault_upgrade.py \
    tests/test_vault_upgrade_cli.py \
    tests/test_main_window.py
  ```
  Expected: Exit 0.
- [ ] **Step 2: Repository Ruff linting**
  ```bash
  ruff check src tests
  ```
  Expected: Exit 0.
- [ ] **Step 3: Targeted headless probe tests**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_vault_upgrade.py::TestInspectVaultVersion -v --tb=short -p no:cacheprovider
  ```
- [ ] **Step 4: Targeted headless CLI tests**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_vault_upgrade_cli.py -v --tb=short -p no:cacheprovider
  ```
- [ ] **Step 5: Targeted headless UI upgrade tests**
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window.py -v --tb=short -p no:cacheprovider -k upgrade
  ```
- [ ] **Step 6: Full headless suite**
  ```bash
  QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider
  ```
- [ ] **Step 7: Bandit on core and CLI only (no -lll)**
  ```bash
  bandit -q -r src/openadmindesk/core/vault_upgrade.py src/openadmindesk/vault_upgrade_cli.py
  ```
  Expected: Exit 0, no findings. No `poetry`, no `-lll`.
- [ ] **Step 8: Diff whitespace check**
  ```bash
  git diff --check
  ```
- [ ] **Step 9: Final status**
  ```bash
  git status --short
  ```
  Expected: Only expected files. No skips accepted for `test_no_pyside6_import` — the subprocess approach must pass.

---

## Task 10: Packaging Verification

**Files:** Only `pyproject.toml` and built wheel.

- [ ] **Step 1: Build wheel and assert entry point in one bash block with cleanup**
  ```bash
  set -euo pipefail
  tmpdir=$(mktemp -d)
  trap "rm -rf '$tmpdir'" EXIT
  python3 -m build --wheel --outdir "$tmpdir"
  python3 - "$tmpdir" <<'PY'
  import os, sys, zipfile
  tmpdir = sys.argv[1]
  wheels = [f for f in os.listdir(tmpdir) if f.endswith(".whl")]
  assert len(wheels) == 1, f"Expected 1 wheel, found {wheels}"
  wheel = os.path.join(tmpdir, wheels[0])
  with zipfile.ZipFile(wheel) as z:
      candidates = [n for n in z.namelist() if n.endswith(".dist-info/entry_points.txt")]
      assert len(candidates) == 1, f"entry_points.txt candidates: {candidates}"
      content = z.read(candidates[0]).decode()
      print(content)
      assert "openadmindesk-vault-upgrade = openadmindesk.vault_upgrade_cli:main" in content, content
  PY
  ```
  Expected: Exit 0. Prints `entry_points.txt` content; assertion passes. Cleanup automatic.
- [ ] **Step 2: Verify no repo artifacts**
  ```bash
  git status --short
  git diff --stat
  ```
  Expected: No build artifacts, only expected files.
- [ ] **Step 3: If build unavailable / nonzero → report NOT_VERIFIED.** Do not skip or fabricate results.

---

## Task 11: Documentation (Only After Verified Behavior)

**Files:** `docs/SECURITY_MODEL.md`, `docs/VAULT_SPEC.md`, `docs/AUDIT_REMEDIATION_PLAN.md`, `docs/WORKLOG.md`.

**No doc changes before Tasks 9-10 pass.**

- [ ] **Step 1: Update `docs/SECURITY_MODEL.md`** — add subsection documenting:
  - `inspect_vault_version` is read-only
  - CLI does not accept passwords via argv
  - CLI JSON includes hashes for scripting consumers
  - UI never displays hashes or secrets
  - Vault stays locked after upgrade
- [ ] **Step 2: Update `docs/VAULT_SPEC.md`** — add note about 9.9d upgrade surface: `inspect_vault_version`, standalone CLI, Qt menu action.
- [ ] **Step 3: Update `docs/AUDIT_REMEDIATION_PLAN.md`** — change `- [ ] 9.9d` to `- [x] 9.9d`.
- [ ] **Step 4: Append concise WORKLOG entry** — follow existing format: implementation summary, files changed, evidence table, reviewer verdict, remaining risks (exclusive-writer coordination, encrypted backup retention, same-password only), `READY_FOR_MANUAL_COMMIT`.
- [ ] **Step 5: Verify docs-only diff**
  ```bash
  git diff --check
  ```

---

## Task 12: Final Whole-Diff Reviewer PASS and Completion Gate

**Files:** All changed files. **No agent commit or push.**

- [ ] **Step 1: Prepare final review dossier** — complete `git diff`, spec, Tasks 9-10 evidence, Task 11 docs.
- [ ] **Step 2: Final reviewer inspects against same 10 criteria plus:**
  - Scope matches expected file list
  - All verification commands exit 0
  - Documentation accurate
- [ ] **Step 3: If finding → return to Task 7 with exact findings (no correction inside Task 12).**
        If PASS → run fresh completion evidence before final report.
- [ ] **Step 4: Run fresh completion evidence after final PASS:**
  ```bash
  QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 pytest -q --tb=short -p no:cacheprovider
  ruff check src tests
  bandit -q -r src/openadmindesk/core/vault_upgrade.py src/openadmindesk/vault_upgrade_cli.py
  python3 -m py_compile \
    src/openadmindesk/core/vault_upgrade.py \
    src/openadmindesk/vault_upgrade_cli.py \
    src/openadmindesk/ui/main_window.py \
    tests/test_vault_upgrade.py \
    tests/test_vault_upgrade_cli.py \
    tests/test_main_window.py
  git diff --check
  git status --short
  ```
  All exit 0.
- [ ] **Step 5: Report:**
  ```markdown
  **FINAL_STATUS: COMPLETE_VERIFIED**
  READY_FOR_MANUAL_COMMIT. No commit or push was performed by the agent.
  ```

---

## Plan Self-Review

**Spec Coverage:** Every requirement from the approved spec (inspect_vault_version read-only, CLI no-secrets-in-argv, UI slot with mockable dialogs, vault stays locked, same-password-only) is covered by at least one task step. No spec requirement is unmapped.

**Placeholder Scan:** Marker Scan: clean; no incomplete instructions or unresolved markers.

**Type/Interface Consistency:** All function signatures, return types, and raised exceptions match the spec and existing 9.9c API exactly. `inspect_vault_version(path: Path) -> int` raises `VaultUpgradeError`. `main(argv=None) -> int`. No invented types.

**Command/Scope Outcome:** Every bash command is a concrete invocation with expected exit code. No `make`, `pip install editable`, `pytest-timeout`, `--no-cache` on ruff, or `-lll` on Bandit. Protected files (pyproject.toml except scripts, lockfiles, generated) are never modified outside declared scope.

## Scope Check

- Expected files: 7 functional/test/config files + 4 docs + spec/plan (WORKLOG overlaps docs). No `test_pyproject_scripts.py`.
- No `Change Password` action, no automatic startup/unlock prompts, no `AccountManager`/`VaultManager` refactoring.
- No dependency or lockfile changes (global constraint). No `pytest-timeout` flag.
- No invented APIs, binary headers, old/new password args, `_vault_manager`, timeout plugin, `make`, `pip install editable`.
- No secrets in any output path. No fictional APIs mentioned.
