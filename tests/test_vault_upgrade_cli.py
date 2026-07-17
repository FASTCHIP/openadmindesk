"""Tests for vault upgrade standalone CLI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import openadmindesk.vault_upgrade_cli as cli


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
        # Mock the _acquire_password function to ensure it's never called
        def mock_acquire_password(args):
            raise AssertionError("_acquire_password should not be called without --confirm-upgrade")
        monkeypatch.setattr(cli, "_acquire_password", mock_acquire_password)
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

    def test_pyproject_has_vault_upgrade_script(self) -> None:
        """Test that pyproject.toml has the vault upgrade script entry."""
        # Read pyproject.toml
        with open("pyproject.toml", "r") as f:
            content = f.read()
        
        # Check that the script is defined
        assert "openadmindesk-vault-upgrade" in content
        assert "vault_upgrade_cli" in content