"""Tests for explicit legacy profile secret migration."""

from __future__ import annotations

import builtins
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

from openadmindesk.core.account import Account
from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_secret_migration import (
    ProfileSecretBackupResult,
    create_profile_secret_backups,
    migrate_plaintext_profile_secrets,
    scan_plaintext_profile_secrets,
)
from openadmindesk.core.profile_store import ProfileStore
from openadmindesk.core.vault_manager import VaultManager

# Make tools directory importable for CLI tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from migrate_profile_secrets import main  # noqa: E402


def _vault(tmp_path) -> VaultManager:
    vault = VaultManager(str(tmp_path / "vault.json"))
    assert vault.setup_master_password("secret-passphrase")
    assert vault.unlock("secret-passphrase")
    return vault


def test_profile_secret_migration_fail_closed(tmp_path) -> None:
    """Migration raises RuntimeError when confirm_cleartext_removal is False."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Test"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    # No confirmation → fail-closed before any backup or mutation
    with pytest.raises(RuntimeError, match="Migration requires confirm_cleartext_removal=True"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=False,
        )

    # No backup artifacts created
    assert not (tmp_path / "backups").exists()
    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Test",)
        ).fetchone()
        assert row[0] == "secret"


def test_scan_plaintext_profile_secrets_no_secrets(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Clean", host="example.com"))

    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 0
    assert report.primary_only == 0
    assert report.gateway_only == 0
    assert report.mixed == 0
    assert len(report.profiles) == 1
    assert report.profiles[0].name == "Clean"
    assert not report.profiles[0].has_password
    assert not report.profiles[0].has_passphrase
    assert not report.profiles[0].has_gateway_password


def test_scan_plaintext_profile_secrets_primary_only(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="PrimaryOnly", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("legacy-pass", "key-pass", "PrimaryOnly"),
        )
        conn.commit()

    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 1
    assert report.primary_only == 1
    assert report.gateway_only == 0
    assert report.mixed == 0
    assert len(report.profiles) == 1
    assert report.profiles[0].name == "PrimaryOnly"
    assert report.profiles[0].has_password
    assert report.profiles[0].has_passphrase
    assert not report.profiles[0].has_gateway_password


def test_scan_plaintext_profile_secrets_gateway_only(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="GatewayOnly", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET rdp_gateway_password = ? WHERE name = ?",
            ("gateway-pass", "GatewayOnly"),
        )
        conn.commit()

    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 1
    assert report.primary_only == 0
    assert report.gateway_only == 1
    assert report.mixed == 0
    assert len(report.profiles) == 1
    assert report.profiles[0].name == "GatewayOnly"
    assert not report.profiles[0].has_password
    assert not report.profiles[0].has_passphrase
    assert report.profiles[0].has_gateway_password


def test_scan_plaintext_profile_secrets_mixed(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Mixed", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ?, rdp_gateway_password = ? WHERE name = ?",
            ("primary-pass", "key-pass", "gateway-pass", "Mixed"),
        )
        conn.commit()

    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 1
    assert report.primary_only == 0
    assert report.gateway_only == 0
    assert report.mixed == 1
    assert len(report.profiles) == 1
    assert report.profiles[0].name == "Mixed"
    assert report.profiles[0].has_password
    assert report.profiles[0].has_passphrase
    assert report.profiles[0].has_gateway_password


def test_scan_plaintext_profile_secrets_with_credential_ids(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Migrated", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET credential_id = ?, rdp_gateway_credential_id = ? WHERE name = ?",
            ("cred-123", "cred-456", "Migrated"),
        )
        conn.commit()

    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 0
    assert report.profiles[0].has_credential_id
    assert report.profiles[0].has_gateway_credential_id


def test_scan_plaintext_profile_secrets_deterministic_order(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Zebra", host="example.com"))
    store.save_profile(Profile(name="Alpha", host="example.com"))
    store.save_profile(Profile(name="Beta", host="example.com"))

    report1 = scan_plaintext_profile_secrets(store.db_path)
    report2 = scan_plaintext_profile_secrets(store.db_path)

    assert [p.name for p in report1.profiles] == [p.name for p in report2.profiles]
    assert report1.profiles[0].name == "Alpha"
    assert report1.profiles[1].name == "Beta"
    assert report1.profiles[2].name == "Zebra"


def test_scan_plaintext_profile_secrets_db_unchanged(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))

    # Get initial database state
    with sqlite3.connect(store.db_path) as conn:
        initial_bytes = conn.iterdump()
        initial_rows = list(conn.execute("SELECT * FROM profiles"))

    # Run scan multiple times
    scan_plaintext_profile_secrets(store.db_path)
    scan_plaintext_profile_secrets(store.db_path)

    # Verify database is unchanged
    with sqlite3.connect(store.db_path) as conn:
        final_bytes = conn.iterdump()
        final_rows = list(conn.execute("SELECT * FROM profiles"))

    assert list(initial_bytes) == list(final_bytes)
    assert initial_rows == final_rows


def test_core_dry_run_scan_text(tmp_path) -> None:
    # Test using the Python API directly instead of subprocess to avoid import issues
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="PrimaryOnly", host="example.com", username="admin"))
    store.save_profile(Profile(name="GatewayOnly", host="example.com", username="admin"))

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("primary-pass", "key-pass", "PrimaryOnly"),
        )
        conn.execute(
            "UPDATE profiles SET rdp_gateway_password = ? WHERE name = ?",
            ("gateway-pass", "GatewayOnly"),
        )
        conn.commit()

    # Test dry-run using the scan function directly
    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 2
    assert report.affected_profiles == 2
    assert report.primary_only == 1
    assert report.gateway_only == 1
    assert report.mixed == 0

    # Find the profiles in the report
    primary_profile = None
    gateway_profile = None
    for profile in report.profiles:
        if profile.name == "PrimaryOnly":
            primary_profile = profile
        elif profile.name == "GatewayOnly":
            gateway_profile = profile

    assert primary_profile is not None
    assert gateway_profile is not None
    assert primary_profile.has_password
    assert primary_profile.has_passphrase
    assert not primary_profile.has_gateway_password
    assert gateway_profile.has_gateway_password
    assert not gateway_profile.has_password
    assert not gateway_profile.has_passphrase


def test_core_dry_run_scan_json(tmp_path) -> None:
    # Test JSON output format using the scan function directly
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="TestProfile", host="example.com", username="admin"))

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("test-pass", "test-key-pass", "TestProfile"),
        )
        conn.commit()

    # Test using the scan function directly
    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 1
    assert report.primary_only == 1
    assert report.profiles[0].name == "TestProfile"
    assert report.profiles[0].has_password
    assert report.profiles[0].has_passphrase
    # Ensure no secret values are in the report
    assert "test-pass" not in str(report)
    assert "test-key-pass" not in str(report)


def test_core_scan_no_password_required(tmp_path) -> None:
    # Test that scan doesn't require password (it never unlocks vault)
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com"))

    # Scan should work without any vault interaction
    report = scan_plaintext_profile_secrets(store.db_path)

    assert report.total_profiles == 1
    assert report.affected_profiles == 0


def test_core_migration_fails_closed(tmp_path) -> None:
    """Migration raises RuntimeError when vault is locked."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Test"),
        )
        conn.commit()

    vault = _vault(tmp_path)
    vault.lock()

    # Vault locked → fail-closed before any backup or mutation
    with pytest.raises(RuntimeError, match="Vault must be unlocked for migration"):
        migrate_plaintext_profile_secrets(
            store.db_path,
            vault,
            confirm_cleartext_removal=True,
        )

    # No backup artifacts created
    assert not (tmp_path / "backups").exists()
    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Test",)
        ).fetchone()
        assert row[0] == "secret"


def test_core_migration_no_legacy_rows(tmp_path) -> None:
    """Migration with no legacy plaintext rows returns zero result, backup=None."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Clean", host="example.com"))

    vault = _vault(tmp_path)
    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )

    assert result.scanned == 0
    assert result.primary_migrated == 0
    assert result.gateway_migrated == 0
    assert result.primary_cleared == 0
    assert result.gateway_cleared == 0
    assert result.backup is None
    assert result.migrated == 0
    assert result.cleared_only == 0


# ── Real CLI tests (call main() directly with capsys) ──────────────────────


def test_cli_dry_run_text(tmp_path, capsys) -> None:
    """CLI dry-run text output contains names/booleans but not secret values."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="SecretBox", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("secret-pass", "key-pass", "SecretBox"),
        )
        conn.commit()

    exit_code = main(["--db", store.db_path, "--dry-run", "--format", "text"])
    captured = capsys.readouterr()

    assert exit_code == 0
    # Profile name visible
    assert "SecretBox" in captured.out
    # Boolean indicators visible
    assert "password=True" in captured.out
    assert "passphrase=True" in captured.out
    # No secret values leaked
    assert "secret-pass" not in captured.out
    assert "key-pass" not in captured.out


def test_cli_dry_run_json(tmp_path, capsys) -> None:
    """CLI dry-run JSON output contains profile names/booleans but not secrets."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="TestProfile", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("test-pass", "test-key-pass", "TestProfile"),
        )
        conn.commit()

    exit_code = main(["--db", store.db_path, "--dry-run", "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["total_profiles"] == 1
    assert data["affected_profiles"] == 1
    assert data["primary_only"] == 1
    assert data["profiles"][0]["name"] == "TestProfile"
    assert data["profiles"][0]["has_password"] is True
    assert data["profiles"][0]["has_passphrase"] is True
    # No secret values in JSON output
    assert "test-pass" not in captured.out
    assert "test-key-pass" not in captured.out


def test_cli_dry_run_no_password(tmp_path, capsys) -> None:
    """CLI dry-run works without any vault password."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com"))

    exit_code = main(["--db", store.db_path, "--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Test" in captured.out


def test_cli_non_dry_run_no_confirmation(tmp_path, capsys) -> None:
    """No --confirm-cleartext-removal → exit 2 before env/vault access,
    DB unchanged."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Test"),
        )
        conn.commit()

    # No vault password needed -- fails closed before any vault/env interaction
    exit_code = main(["--db", store.db_path])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "confirm-cleartext-removal" in captured.err.lower()

    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Test",)
        ).fetchone()
        assert row[0] == "secret"

    # No backup artifacts created
    assert not (tmp_path / "backups").exists()


def test_cli_dry_run_db_unchanged(tmp_path, capsys) -> None:
    """CLI dry-run does not modify the database."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret-value", "Test"),
        )
        conn.commit()

    # Capture database state before CLI call
    with sqlite3.connect(store.db_path) as conn:
        before = list(conn.execute("SELECT * FROM profiles ORDER BY name"))

    exit_code = main(["--db", store.db_path, "--dry-run"])
    assert exit_code == 0
    _ = capsys.readouterr()  # discard output

    # Capture database state after CLI call
    with sqlite3.connect(store.db_path) as conn:
        after = list(conn.execute("SELECT * FROM profiles ORDER BY name"))

    assert before == after


# ── CLI migration tests (gated live-migration) ────────────────────────────────


def test_cli_migration_missing_env(tmp_path, capsys, monkeypatch) -> None:
    """--confirm-cleartext-removal given but env not set → exit 2,
    DB unchanged."""
    monkeypatch.delenv("OPENADMINDESK_VAULT_PASSWORD", raising=False)

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Test"),
        )
        conn.commit()

    exit_code = main([
        "--db", store.db_path,
        "--confirm-cleartext-removal",
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "environment variable" in captured.err.lower()

    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Test",)
        ).fetchone()
        assert row[0] == "secret"

    # No backup artifacts
    assert not (tmp_path / "backups").exists()


def test_cli_migration_wrong_password(tmp_path, capsys, monkeypatch) -> None:
    """Wrong vault password → exit 1, no backup or DB mutation."""
    vault_path = str(tmp_path / "vault.json")
    vault = VaultManager(vault_path)
    assert vault.setup_master_password("correct-password")
    vault.lock()

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Test"),
        )
        conn.commit()

    monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "wrong-password")

    exit_code = main([
        "--db", store.db_path,
        "--vault", vault_path,
        "--confirm-cleartext-removal",
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "vault unlock failed" in captured.err.lower()

    # No backup artifacts created
    assert not (tmp_path / "backups").exists()

    # DB secrets unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Test",)
        ).fetchone()
        assert row[0] == "secret"


def test_cli_migration_text_success(tmp_path, capsys, monkeypatch) -> None:
    """Successful text migration with env password+backup-dir → exit 0,
    no secret values in output, credential IDs set, DB secrets NULL, backups
    exist."""
    vault_path = str(tmp_path / "vault.json")
    vault = VaultManager(vault_path)
    assert vault.setup_master_password("correct-password")
    assert vault.unlock("correct-password")
    vault.lock()

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="PrimaryBox",
        host="host.example.com",
        username="admin",
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ?, "
            "rdp_gateway_password = ? WHERE name = ?",
            ("primary-pass", "key-pass", "gateway-pass", "PrimaryBox"),
        )
        conn.commit()

    backup_dir = str(tmp_path / "my_backups")
    monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "correct-password")

    exit_code = main([
        "--db", store.db_path,
        "--vault", vault_path,
        "--confirm-cleartext-removal",
        "--backup-dir", backup_dir,
    ])
    captured = capsys.readouterr()

    assert exit_code == 0, f"exit_code={exit_code}, stderr={captured.err}"

    # No secret values in output
    assert "primary-pass" not in captured.out
    assert "key-pass" not in captured.out
    assert "gateway-pass" not in captured.out

    # Print includes counts
    assert "Primary secrets migrated: 1" in captured.out
    assert "Gateway secrets migrated: 1" in captured.out
    assert "Backup database:" in captured.out
    assert "Backup vault:" in captured.out

    # Credential IDs set in DB
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", ("PrimaryBox",)
        ).fetchone()
        assert row["credential_id"] is not None
        assert row["rdp_gateway_credential_id"] is not None
        # DB secrets NULLed
        assert row["password"] is None
        assert row["private_key_passphrase"] is None
        assert row["rdp_gateway_password"] is None

    # Backups exist in specified directory
    assert Path(backup_dir).exists()
    assert len(list(Path(backup_dir).iterdir())) >= 2


def test_cli_migration_json_success(tmp_path, capsys, monkeypatch) -> None:
    """Successful JSON migration output parses counts, backup paths, and
    hashes; no secret values."""
    vault_path = str(tmp_path / "vault.json")
    vault = VaultManager(vault_path)
    assert vault.setup_master_password("master-pass")
    assert vault.unlock("master-pass")
    vault.lock()

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="JsonBox",
        host="json.example.com",
        username="admin",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("json-secret", "JsonBox"),
        )
        conn.commit()

    monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "master-pass")

    exit_code = main([
        "--db", store.db_path,
        "--vault", vault_path,
        "--confirm-cleartext-removal",
        "--format", "json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)

    assert data["scanned"] == 1
    assert data["primary_migrated"] == 1
    assert data["gateway_migrated"] == 0
    assert data["backup"] is not None
    assert "db_backup_path" in data["backup"]
    assert "vault_backup_path" in data["backup"]
    assert "db_sha256" in data["backup"]
    assert "vault_sha256" in data["backup"]

    # Backup files exist on disk
    assert os.path.isfile(data["backup"]["db_backup_path"])
    assert os.path.isfile(data["backup"]["vault_backup_path"])

    # No secret values in output
    assert "json-secret" not in captured.out


def test_cli_migration_conflict(tmp_path, capsys, monkeypatch) -> None:
    """Conflict between existing vault account and profile plaintext → exit 1,
    DB/vault unchanged, backups remain, no secret in stderr."""
    vault_path = str(tmp_path / "vault.json")
    vault = VaultManager(vault_path)
    assert vault.setup_master_password("master-pass")
    assert vault.unlock("master-pass")

    # Pre-seed vault account with DIFFERENT password than profile
    acct = Account(
        name="Conflict", username="admin", host="conflict.example.com",
        password="different-vault-pass", service_type="ssh",
    )
    assert vault.add_account(acct)
    vault.lock()

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="Conflict",
        host="conflict.example.com",
        username="admin",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, credential_id = ? WHERE name = ?",
            ("profile-pass", acct.id, "Conflict"),
        )
        conn.commit()

    monkeypatch.setenv("OPENADMINDESK_VAULT_PASSWORD", "master-pass")

    exit_code = main([
        "--db", store.db_path,
        "--vault", vault_path,
        "--confirm-cleartext-removal",
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "different secret values" in captured.err

    # No secret values in stderr
    assert "profile-pass" not in captured.err
    assert "different-vault-pass" not in captured.err

    # DB unchanged (secrets still in DB)
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Conflict",)
        ).fetchone()
        assert row[0] == "profile-pass"

    # Vault unchanged
    vault2 = VaultManager(vault_path)
    assert vault2.unlock("master-pass")
    accounts = vault2.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].password == "different-vault-pass"

    # Backups remain on disk (created before conflict detection)
    assert (tmp_path / "backups").exists()
    assert len(list((tmp_path / "backups").iterdir())) >= 2


# ── Phase 9.6b: Secure SQLite+vault backup primitives ────────────────────────


def _setup_profile_and_vault(
    tmp_path: Path,
) -> tuple[str, str, VaultManager]:
    """Create a profile store with a legacy plaintext secret row and an
    encrypted vault containing an account. Returns (db_path, vault_path, vault)."""
    vault_path = str(tmp_path / "vault.json")
    vault = VaultManager(vault_path)
    assert vault.setup_master_password("test-master-pass")
    assert vault.unlock("test-master-pass")

    acct = Account(
        name="test-account",
        username="root",
        password="secret-password",
        host="backup-test.example.com",
        service_type="ssh",
    )
    assert vault.add_account(acct)

    db_path = str(tmp_path / "profiles.db")
    store = ProfileStore(db_path)
    store.save_profile(
        Profile(
            name="LegacyBox",
            host="legacy.example.com",
            username="admin",
        )
    )
    # Inject a legacy plaintext secret directly into the database
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("old-plaintext-pass", "old-key-pass", "LegacyBox"),
        )
        conn.commit()

    vault.lock()

    return db_path, vault_path, vault


def _assert_mode_0600(path: str) -> None:
    """Assert a file has exactly mode 0600 (owner rw, no group/other)."""
    mode = os.stat(path).st_mode
    assert stat.S_IMODE(mode) == 0o600, (
        f"Expected 0600, got {oct(stat.S_IMODE(mode))} for {path}"
    )


# -- 9.6b Tests ---------------------------------------------------------------


class TestProfileSecretBackups:
    """Phase 9.6b: Secure SQLite+vault backup primitives."""

    def test_backup_contains_legacy_row_and_passes_integrity(
        self, tmp_path: Path
    ) -> None:
        """DB backup has seeded legacy row; integrity_check is ok."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)
        result = create_profile_secret_backups(db_path, vault_path)

        # Backup contains the legacy row
        with sqlite3.connect(result.db_backup_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT name, password, private_key_passphrase FROM profiles"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["name"] == "LegacyBox"
            assert rows[0]["password"] == "old-plaintext-pass"
            assert rows[0]["private_key_passphrase"] == "old-key-pass"

            row = conn.execute("PRAGMA integrity_check").fetchone()
            assert row[0] == "ok"

    def test_backup_vault_unlocks_independently(
        self, tmp_path: Path
    ) -> None:
        """Encrypted vault backup can be opened independently and contains the
        expected account."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)

        # Capture expected account data from the source vault
        source_vault = VaultManager(vault_path)
        assert source_vault.unlock("test-master-pass")
        accounts = source_vault.get_all_accounts()
        assert len(accounts) == 1
        expected_id = accounts[0].id
        expected_name = accounts[0].name
        expected_password = accounts[0].password
        source_vault.lock()

        result = create_profile_secret_backups(db_path, vault_path)

        # Open the backup as a completely independent vault
        backup_vault = VaultManager(result.vault_backup_path)
        assert backup_vault.unlock("test-master-pass")
        backup_accounts = backup_vault.get_all_accounts()
        assert len(backup_accounts) == 1
        assert backup_accounts[0].id == expected_id
        assert backup_accounts[0].name == expected_name
        assert backup_accounts[0].password == expected_password

    def test_backup_files_mode_0600(self, tmp_path: Path) -> None:
        """Both backup files have exactly mode 0600."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)
        result = create_profile_secret_backups(db_path, vault_path)

        _assert_mode_0600(result.db_backup_path)
        _assert_mode_0600(result.vault_backup_path)

    def test_backup_dir_mode_0700(self, tmp_path: Path) -> None:
        """New backup directory has mode 0700 (no group/world bits)."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)

        # Ensure no pre-existing backups dir
        backups_dir = tmp_path / "backups"
        assert not backups_dir.exists()

        create_profile_secret_backups(
            db_path, vault_path, backup_dir=str(backups_dir)
        )

        mode = os.stat(str(backups_dir)).st_mode
        perm = stat.S_IMODE(mode)
        assert perm == 0o700, (
            f"Expected 0700, got {oct(perm)} for {backups_dir}"
        )

    def test_backup_default_dir_is_db_parent_backups(
        self, tmp_path: Path
    ) -> None:
        """Default backup directory is <db_parent>/backups."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)
        result = create_profile_secret_backups(db_path, vault_path)

        expected_dir = str(tmp_path / "backups")
        assert Path(result.db_backup_path).parent == Path(expected_dir)
        assert Path(result.vault_backup_path).parent == Path(expected_dir)

    def test_backup_two_calls_unique_paths(self, tmp_path: Path) -> None:
        """Two successive backup calls produce different paths (no overwrite)."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)

        result1 = create_profile_secret_backups(db_path, vault_path)
        result2 = create_profile_secret_backups(db_path, vault_path)

        assert result1.db_backup_path != result2.db_backup_path
        assert result1.vault_backup_path != result2.vault_backup_path
        # Both backup files exist
        assert os.path.isfile(result1.db_backup_path)
        assert os.path.isfile(result1.vault_backup_path)
        assert os.path.isfile(result2.db_backup_path)
        assert os.path.isfile(result2.vault_backup_path)

    def test_backup_missing_db_fails_no_artifacts(
        self, tmp_path: Path
    ) -> None:
        """Missing DB raises RuntimeError before creating any artifacts."""
        vault_path = str(tmp_path / "vault.json")
        _vault = VaultManager(vault_path)
        assert _vault.setup_master_password("test-master-pass")

        missing_db = str(tmp_path / "nonexistent.db")

        with pytest.raises(RuntimeError, match="not a regular file"):
            create_profile_secret_backups(missing_db, vault_path)

        # No backup directory created
        backups_dir = tmp_path / "backups"
        assert not backups_dir.exists()

    def test_backup_missing_vault_fails_no_artifacts(
        self, tmp_path: Path
    ) -> None:
        """Missing vault raises RuntimeError before creating any artifacts."""
        db_path = str(tmp_path / "profiles.db")
        ProfileStore(db_path)

        missing_vault = str(tmp_path / "nonexistent.json")

        with pytest.raises(RuntimeError, match="not a regular file"):
            create_profile_secret_backups(db_path, missing_vault)

        backups_dir = tmp_path / "backups"
        assert not backups_dir.exists()

    def test_backup_vault_copy_failure_cleans_both(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Simulated vault copy failure after DB backup cleans both files."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)

        # Replace builtins.open so the first open() call (vault read) fails.
        # sqlite3 and tempfile.mkstemp use low-level C file ops, not builtins.open.
        call_count = 0

        def _failing_open(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            raise OSError("Simulated vault read failure")

        monkeypatch.setattr(builtins, "open", _failing_open)

        with pytest.raises(RuntimeError):
            create_profile_secret_backups(db_path, vault_path)

        # Backup directory exists but contains no leftover files
        backups_dir = tmp_path / "backups"
        assert backups_dir.exists()
        children = list(backups_dir.iterdir())
        assert children == [], f"Expected empty backup dir, got {children}"

    def test_backup_hashes_match_expected(
        self, tmp_path: Path
    ) -> None:
        """Returned hashes are correct for both backup files."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)

        # Unlock vault to verify account, then lock again for backup
        source_vault = VaultManager(vault_path)
        assert source_vault.unlock("test-master-pass")
        source_vault.lock()

        result = create_profile_secret_backups(db_path, vault_path)

        # Re-compute and verify
        import hashlib

        def _sha256(p: str) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()

        assert result.db_sha256 == _sha256(result.db_backup_path)
        assert result.vault_sha256 == _sha256(result.vault_backup_path)
        # Vault backup hash equals source vault hash (binary identical)
        assert result.vault_sha256 == _sha256(vault_path)

    def test_backup_no_json_plaintext_artifacts(
        self, tmp_path: Path
    ) -> None:
        """No .json report files are created by the backup process."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)
        result = create_profile_secret_backups(db_path, vault_path)

        # The vault backup has .json suffix (it is the encrypted vault copy),
        # but there should be no additional .json report files.
        items = list(Path(result.db_backup_path).parent.iterdir())
        json_files = [p for p in items if p.suffix == ".json"]
        # Exactly one json file: the vault backup
        assert len(json_files) == 1
        assert json_files[0].name == Path(
            result.vault_backup_path
        ).name

    def test_backup_special_chars_in_path(
        self, tmp_path: Path
    ) -> None:
        """DB path and backup dir containing spaces, ? and # work correctly."""
        special_dir = tmp_path / "backup dir with #? and spaces"
        special_dir.mkdir(parents=True, exist_ok=True)

        db_path = str(special_dir / "my db file?.db")
        vault_path = str(special_dir / "my vault#.json")

        # Create source files with special chars in paths
        store = ProfileStore(db_path)
        store.save_profile(
            Profile(name="SpecialPath", host="example.com", username="admin")
        )
        # Inject legacy plaintext secret
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE profiles SET password = ? WHERE name = ?",
                ("secret-value", "SpecialPath"),
            )
            conn.commit()

        vault = VaultManager(vault_path)
        assert vault.setup_master_password("test-master-pass")
        assert vault.unlock("test-master-pass")
        acct = Account(
            name="test-account",
            username="root",
            password="special-password",
            host="example.com",
            service_type="ssh",
        )
        assert vault.add_account(acct)
        vault.lock()

        # Run backup with a backup dir containing special chars
        backup_subdir = tmp_path / "my backups (#?)"
        result = create_profile_secret_backups(
            db_path, vault_path, backup_dir=str(backup_subdir)
        )

        # Verify backup files exist and have correct content
        assert os.path.isfile(result.db_backup_path)
        assert os.path.isfile(result.vault_backup_path)

        # DB backup contains the row
        with sqlite3.connect(result.db_backup_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT name FROM profiles"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["name"] == "SpecialPath"
            row = conn.execute("PRAGMA integrity_check").fetchone()
            assert row[0] == "ok"

        # Vault backup unlocks independently
        backup_vault = VaultManager(result.vault_backup_path)
        assert backup_vault.unlock("test-master-pass")
        accounts = backup_vault.get_all_accounts()
        assert len(accounts) == 1
        assert (
            accounts[0].password == "special-password"
        )

        # Hashes are valid
        import hashlib

        def _sha256(p: str) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()

        assert result.db_sha256 == _sha256(
            result.db_backup_path
        )
        assert result.vault_sha256 == _sha256(
            result.vault_backup_path
        )

    def test_backup_symlink_db_rejected(
        self, tmp_path: Path
    ) -> None:
        """Symlink database path is rejected with no backup artifacts."""
        try:
            os.symlink(
                str(tmp_path / "nonexistent_target"),
                str(tmp_path / "db_symlink.db"),
            )
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this filesystem")

        vault_path = str(tmp_path / "vault.json")
        _vault = VaultManager(vault_path)
        assert _vault.setup_master_password("test-master-pass")

        symlink_db = str(tmp_path / "db_symlink.db")

        with pytest.raises(RuntimeError, match="symbolic link"):
            create_profile_secret_backups(symlink_db, vault_path)

        # No backup directory or artifacts created
        backups_dir = tmp_path / "backups"
        assert not backups_dir.exists()

    def test_backup_symlink_vault_rejected(
        self, tmp_path: Path
    ) -> None:
        """Symlink vault path is rejected with no backup artifacts."""
        db_path = str(tmp_path / "profiles.db")
        store = ProfileStore(db_path)
        store.save_profile(Profile(name="Test", host="example.com"))

        try:
            os.symlink(
                str(tmp_path / "nonexistent_target"),
                str(tmp_path / "vault_symlink.json"),
            )
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this filesystem")

        symlink_vault = str(tmp_path / "vault_symlink.json")

        with pytest.raises(RuntimeError, match="symbolic link"):
            create_profile_secret_backups(db_path, symlink_vault)

        # No backup directory or artifacts created
        backups_dir = tmp_path / "backups"
        assert not backups_dir.exists()

    def test_backup_result_is_frozen_dataclass(
        self, tmp_path: Path
    ) -> None:
        """ProfileSecretBackupResult is a frozen dataclass with the expected attributes."""
        db_path, vault_path, _ = _setup_profile_and_vault(tmp_path)
        result = create_profile_secret_backups(db_path, vault_path)

        assert isinstance(result, ProfileSecretBackupResult)
        with pytest.raises(AttributeError):
            result.db_backup_path = "/different/path"  # type: ignore[misc]


# ── Phase 9.6c: Compensated primary+gateway migration integration tests ────

# Test 1: confirmation false / vault locked → no backup, no mutation


def test_migration_preconditions_fail_closed(tmp_path: Path) -> None:
    """Confirm_cleartext_removal=False and locked vault both raise before any
    side effects; no backup artifacts or DB mutations."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Target", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "Target"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    # -- confirm_cleartext_removal=False --
    with pytest.raises(RuntimeError, match="Migration requires confirm_cleartext_removal=True"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=False,
        )
    # No backup artifacts
    assert not (tmp_path / "backups").exists()
    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Target",)
        ).fetchone()
        assert row[0] == "secret"

    # -- vault locked --
    vault.lock()
    with pytest.raises(RuntimeError, match="Vault must be unlocked for migration"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )
    assert not (tmp_path / "backups").exists()
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Target",)
        ).fetchone()
        assert row[0] == "secret"


# Test 2: no legacy rows → zero result, backup None


def test_migration_no_legacy_rows(tmp_path: Path) -> None:
    """No plaintext secrets in DB → result.scanned=0, backup=None."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Clean", host="example.com"))
    vault = _vault(tmp_path)
    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )
    assert result.scanned == 0
    assert result.backup is None
    assert result.migrated == 0
    assert result.cleared_only == 0


# Test 3: primary-only → vault account, credential_id set, DB secrets cleared


def test_migration_primary_only(tmp_path: Path) -> None:
    """Primary-only profile: vault account created, DB secrets NULLed,
    backup present, counts correct."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="PrimaryOnly", host="host.example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ? WHERE name = ?",
            ("legacy-pass", "key-pass", "PrimaryOnly"),
        )
        conn.commit()

    vault = _vault(tmp_path)
    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )

    assert result.scanned == 1
    assert result.primary_migrated == 1
    assert result.gateway_migrated == 0
    assert result.primary_cleared == 0
    assert result.gateway_cleared == 0
    assert result.backup is not None

    # Vault account created with correct properties
    accounts = vault.get_all_accounts()
    assert len(accounts) == 1
    acct = accounts[0]
    assert acct.name == "PrimaryOnly"
    assert acct.username == "admin"
    assert acct.host == "host.example.com"
    assert acct.service_type == "ssh"
    assert acct.password == "legacy-pass"
    assert acct.private_key_passphrase == "key-pass"

    # DB secrets cleared, credential_id set
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", ("PrimaryOnly",)
        ).fetchone()
        assert row["credential_id"] == acct.id
        assert row["password"] is None
        assert row["private_key_passphrase"] is None

    # Backup dir exists with files
    backups_dir = tmp_path / "backups"
    assert backups_dir.exists()
    backup_files = list(backups_dir.iterdir())
    assert len(backup_files) >= 2


# Test 4: gateway-only → separate rdp-gateway vault account


def test_migration_gateway_only(tmp_path: Path) -> None:
    """Gateway-only profile: rdp-gateway vault account created, gateway
    password cleared in DB."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="GatewayOnly",
        host="host.example.com",
        username="admin",
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET rdp_gateway_password = ? WHERE name = ?",
            ("gateway-pass", "GatewayOnly"),
        )
        conn.commit()

    vault = _vault(tmp_path)
    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )

    assert result.scanned == 1
    assert result.primary_migrated == 0
    assert result.gateway_migrated == 1
    assert result.primary_cleared == 0
    assert result.gateway_cleared == 0
    assert result.backup is not None

    accounts = vault.get_all_accounts()
    assert len(accounts) == 1
    acct = accounts[0]
    assert acct.name == "GatewayOnly-gateway"
    assert acct.username == "gw-user"
    assert acct.host == "gw.example.com"
    assert acct.service_type == "rdp-gateway"
    assert acct.password == "gateway-pass"

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", ("GatewayOnly",)
        ).fetchone()
        assert row["rdp_gateway_credential_id"] == acct.id
        assert row["rdp_gateway_password"] is None


# Test 5: mixed → both accounts, both credential IDs, all secrets NULLed


def test_migration_mixed(tmp_path: Path) -> None:
    """Mixed primary+gateway profile: both vault accounts created, both
    credential IDs set, all three secret columns NULLed."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="Mixed",
        host="mixed.example.com",
        username="admin",
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ?, "
            "rdp_gateway_password = ? WHERE name = ?",
            ("primary-pass", "key-pass", "gateway-pass", "Mixed"),
        )
        conn.commit()

    vault = _vault(tmp_path)
    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )

    assert result.scanned == 1
    assert result.primary_migrated == 1
    assert result.gateway_migrated == 1
    assert result.primary_cleared == 0
    assert result.gateway_cleared == 0
    assert result.backup is not None

    accounts = vault.get_all_accounts()
    assert len(accounts) == 2
    primary = next(a for a in accounts if a.service_type == "ssh")
    gateway = next(a for a in accounts if a.service_type == "rdp-gateway")

    assert primary.password == "primary-pass"
    assert primary.private_key_passphrase == "key-pass"
    assert primary.name == "Mixed"
    assert primary.host == "mixed.example.com"

    assert gateway.password == "gateway-pass"
    assert gateway.name == "Mixed-gateway"
    assert gateway.host == "gw.example.com"

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", ("Mixed",)
        ).fetchone()
        assert row["credential_id"] == primary.id
        assert row["rdp_gateway_credential_id"] == gateway.id
        assert row["password"] is None
        assert row["private_key_passphrase"] is None
        assert row["rdp_gateway_password"] is None


# Test 6: existing matching accounts → no vault rewrite, cleared counts only


def test_migration_existing_matching_accounts(tmp_path: Path) -> None:
    """Pre-existing matching vault accounts produce clear-only results; no
    duplicate accounts or vault rewrites."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="Matched",
        host="match.example.com",
        username="admin",
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, private_key_passphrase = ?, "
            "rdp_gateway_password = ? WHERE name = ?",
            ("pass", "key-pass", "gw-pass", "Matched"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    # Pre-create matching vault accounts
    primary = Account(
        name="Matched", username="admin", host="match.example.com",
        password="pass", private_key_passphrase="key-pass",
        service_type="ssh",
    )
    assert vault.add_account(primary)
    gateway = Account(
        name="Matched-gateway", username="gw-user", host="gw.example.com",
        password="gw-pass", service_type="rdp-gateway",
    )
    assert vault.add_account(gateway)

    # Set credential IDs in DB so resolver finds them
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET credential_id = ?, rdp_gateway_credential_id = ? WHERE name = ?",
            (primary.id, gateway.id, "Matched"),
        )
        conn.commit()

    accounts_before = vault.get_all_accounts()
    assert len(accounts_before) == 2

    result = migrate_plaintext_profile_secrets(
        store.db_path, vault, confirm_cleartext_removal=True,
    )

    assert result.scanned == 1
    assert result.primary_migrated == 0
    assert result.gateway_migrated == 0
    assert result.primary_cleared == 1
    assert result.gateway_cleared == 1

    # No new vault accounts added
    accounts_after = vault.get_all_accounts()
    assert len(accounts_after) == 2
    # Original accounts unchanged
    assert next(a for a in accounts_after if a.id == primary.id).password == "pass"

    # DB secrets cleared
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", ("Matched",)
        ).fetchone()
        assert row["password"] is None
        assert row["private_key_passphrase"] is None
        assert row["rdp_gateway_password"] is None
        # Credential IDs preserved
        assert row["credential_id"] == primary.id
        assert row["rdp_gateway_credential_id"] == gateway.id


# Test 7: conflict → raises, DB/vault unchanged, backup remains


def test_migration_conflict_raises(tmp_path: Path) -> None:
    """Vault account with different secrets than profile raises RuntimeError;
    DB and vault unchanged; backup files remain on disk."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="Conflict", host="example.com", username="admin",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("profile-pass", "Conflict"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    # Pre-create vault account with a DIFFERENT password
    acct = Account(
        name="Conflict", username="admin", host="example.com",
        password="different-vault-pass", service_type="ssh",
    )
    assert vault.add_account(acct)

    # Set credential_id to reference the conflict account
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET credential_id = ? WHERE name = ?",
            (acct.id, "Conflict"),
        )
        conn.commit()

    with pytest.raises(RuntimeError, match="different secret values"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    # DB unchanged (secrets still there)
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("Conflict",)
        ).fetchone()
        assert row[0] == "profile-pass"

    # Vault unchanged (still has pre-existing account with different password)
    accounts = vault.get_all_accounts()
    assert len(accounts) == 1
    assert accounts[0].password == "different-vault-pass"

    # Backup files remain (created before conflict detection)
    backups_dir = tmp_path / "backups"
    assert backups_dir.exists()
    assert len(list(backups_dir.iterdir())) >= 2


# Test 8: gateway add fails → primary compensated, DB unchanged


def test_migration_gateway_failure_compensates_primary(tmp_path: Path, monkeypatch) -> None:
    """When gateway add_account returns False after primary success, the
    primary vault account is removed (compensated) and DB remains unchanged."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(
        name="FailBox",
        host="example.com",
        username="admin",
        rdp_gateway="gw.example.com",
        rdp_gateway_username="gw-user",
    ))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ?, rdp_gateway_password = ? WHERE name = ?",
            ("primary-pass", "gateway-pass", "FailBox"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    original_add = vault.add_account
    call_count = [0]

    def _failing_add(acct: object) -> bool:
        call_count[0] += 1
        if call_count[0] == 2:  # 2nd call = gateway add → fail
            return False
        return original_add(acct)

    monkeypatch.setattr(vault, "add_account", _failing_add)

    with pytest.raises(RuntimeError, match="Failed to add"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    # Primary account removed via compensation
    assert vault.get_all_accounts() == []

    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password, rdp_gateway_password FROM profiles WHERE name = ?",
            ("FailBox",),
        ).fetchone()
        assert row[0] == "primary-pass"
        assert row[1] == "gateway-pass"


# Test 9: DB UPDATE failure via SQLite trigger → all accounts removed,
#          DB unchanged, backups remain


def test_migration_db_update_failure_compensates(tmp_path: Path) -> None:
    """When the DB UPDATE fails (via SQLite trigger), all vault accounts
    created during migration are removed, DB secrets remain intact, and
    backup files survive."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="TriggerBox", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret", "TriggerBox"),
        )
        # Trigger that rejects any UPDATE on profiles
        conn.execute("""
            CREATE TRIGGER reject_update AFTER UPDATE ON profiles
            BEGIN
                SELECT RAISE(ABORT, 'Trigger rejected update');
            END
        """)
        conn.commit()

    vault = _vault(tmp_path)

    # When compensation succeeds, the raw IntegrityError is re-raised
    with pytest.raises((RuntimeError, sqlite3.IntegrityError)):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    # All vault accounts removed
    assert vault.get_all_accounts() == []

    # DB secrets unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("TriggerBox",)
        ).fetchone()
        assert row[0] == "secret"

    # Backup files remain on disk
    backups_dir = tmp_path / "backups"
    assert backups_dir.exists()
    assert len(list(backups_dir.iterdir())) >= 2


# Test 10: multiple profiles, later failure → prior accounts compensated,
#          all DB unchanged


def test_migration_multiple_profiles_later_failure_compensates_all(
    tmp_path: Path, monkeypatch,
) -> None:
    """When processing multiple profiles and one later add fails, all prior
    vault accounts are compensated (removed) and all DB rows are unchanged."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    for i in range(3):
        store.save_profile(Profile(
            name=f"Profile{i}", host="example.com", username="admin",
        ))
    with sqlite3.connect(store.db_path) as conn:
        for i in range(3):
            conn.execute(
                "UPDATE profiles SET password = ? WHERE name = ?",
                (f"secret-{i}", f"Profile{i}"),
            )
        conn.commit()

    vault = _vault(tmp_path)

    original_add = vault.add_account
    call_count = [0]

    def _failing_add(acct: object) -> bool:
        call_count[0] += 1
        if call_count[0] == 3:  # 3rd add = third profile → fail
            return False
        return original_add(acct)

    monkeypatch.setattr(vault, "add_account", _failing_add)

    with pytest.raises(RuntimeError):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    # All accounts compensated
    assert vault.get_all_accounts() == []

    # All DB secrets unchanged
    with sqlite3.connect(store.db_path) as conn:
        for i in range(3):
            row = conn.execute(
                "SELECT password FROM profiles WHERE name = ?",
                (f"Profile{i}",),
            ).fetchone()
            assert row[0] == f"secret-{i}", (
                f"Profile{i} secret was modified"
            )


# Test 11: compensation remove_account returns False while account exists
#          → RuntimeError mentions compensation + backup paths, no secret text


def test_migration_compensation_failure_mentions_backup_paths(
    tmp_path: Path, monkeypatch,
) -> None:
    """When vault.remove_account returns False and account still exists,
    RuntimeError includes 'compensation' and 'Backup paths' but no raw
    secret values."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="BadComp", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret-value", "BadComp"),
        )
        # Trigger to make DB update fail, forcing compensation
        conn.execute("""
            CREATE TRIGGER fail_update AFTER UPDATE ON profiles
            BEGIN
                SELECT RAISE(ABORT, 'Simulated DB failure');
            END
        """)
        conn.commit()

    vault = _vault(tmp_path)

    # Make remove_account always return False
    monkeypatch.setattr(vault, "remove_account", lambda account_id: False)

    with pytest.raises(RuntimeError) as exc_info:
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    msg = str(exc_info.value)
    assert "compensation" in msg.lower() or "Compensation" in msg
    assert "Backup paths" in msg
    # No raw secret values in error
    assert "secret-value" not in msg
    assert "secret" not in msg.lower() or "different" in msg.lower()

    # DB unchanged
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT password FROM profiles WHERE name = ?", ("BadComp",)
        ).fetchone()
        assert row[0] == "secret-value"

    # Backup files remain
    assert (tmp_path / "backups").exists()


# Test 12: vault locks mid-run → rollback, DB unchanged


def test_migration_vault_locks_mid_run_rolls_back(
    tmp_path: Path, monkeypatch,
) -> None:
    """Vault auto-lock during migration (is_unlocked returns False mid-run)
    triggers a RuntimeError.  All vault accounts are compensated and DB
    secrets remain intact."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Alpha", host="example.com", username="admin"))
    store.save_profile(Profile(name="Beta", host="example.com", username="admin"))
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret-a", "Alpha"),
        )
        conn.execute(
            "UPDATE profiles SET password = ? WHERE name = ?",
            ("secret-b", "Beta"),
        )
        conn.commit()

    vault = _vault(tmp_path)

    # Simulate vault lock after processing the first profile
    call_count = [0]

    def _locking_unlocked() -> bool:
        call_count[0] += 1
        # Call 1: pre-check (True).  Call 2: Alpha row (True).  Call 3: Beta row (False).
        return call_count[0] < 3

    monkeypatch.setattr(vault, "is_unlocked", _locking_unlocked)

    with pytest.raises(RuntimeError, match="Vault became locked"):
        migrate_plaintext_profile_secrets(
            store.db_path, vault, confirm_cleartext_removal=True,
        )

    # DB unchanged — no credential IDs set, secrets intact
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT name, password, credential_id FROM profiles ORDER BY name",
        ).fetchall()
        assert rows[0]["password"] == "secret-a"
        assert rows[1]["password"] == "secret-b"
        for row in rows:
            assert row["credential_id"] is None, (
                f"{row['name']} has credential_id set despite rollback"
            )

    # Vault accounts compensated
    assert vault.get_all_accounts() == []
