"""Tests for explicit legacy profile secret migration."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_secret_migration import (
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
    store = ProfileStore(str(tmp_path / "profiles.db"))
    vault = _vault(tmp_path)

    # Live migration is disabled pending safe compensated migration
    with pytest.raises(RuntimeError, match="live migration is disabled"):
        migrate_plaintext_profile_secrets(store.db_path, vault, confirm_cleartext_removal=True)


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
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com", username="admin"))

    vault = _vault(tmp_path)

    # Test that non-dry-run fails closed even with unlocked vault
    with pytest.raises(RuntimeError, match="live migration is disabled"):
        migrate_plaintext_profile_secrets(
            store.db_path,
            vault,
            confirm_cleartext_removal=True,
        )


def test_core_migration_no_password_fails(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com"))

    vault = _vault(tmp_path)

    # Test that migration fails closed before requiring confirmation
    with pytest.raises(RuntimeError, match="live migration is disabled"):
        migrate_plaintext_profile_secrets(
            store.db_path,
            vault,
            confirm_cleartext_removal=False,
        )


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


def test_cli_non_dry_run_fails_closed(tmp_path, capsys) -> None:
    """CLI non-dry-run prints disabled message to stderr and returns 1."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.save_profile(Profile(name="Test", host="example.com"))

    # No vault password needed -- fails closed before any vault interaction
    exit_code = main(["--db", store.db_path])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "disabled" in captured.err.lower()
    assert "dry-run" in captured.err.lower()


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
