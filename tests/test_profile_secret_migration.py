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
