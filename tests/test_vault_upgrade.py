"""Tests for vault upgrade functionality."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pytest

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from openadmindesk.core.account import Account
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.core.vault_upgrade import (
    VaultUpgradeError,
    VaultUpgradeResult,
    inspect_vault_version,
    upgrade_vault_v1_to_v2,
    _BackupInfo,
    _account_map,
    _build_v2_candidate,
    _create_secure_backup,
    _load_source_document,
    _sha256_file,
    _snapshot_v1_accounts,
    _validate_raw_accounts,
    _verify_v2_accounts,
)
import openadmindesk.core.vault_upgrade as vault_upgrade_module

FAKE_PASSWORD = "my_secret_password_123"


def _write_v1_vault(path: Path, password: str, accounts: tuple[Account, ...] = ()) -> bytes:
    salt = secrets.token_bytes(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode())
    key_hash = hashlib.sha256(key).hexdigest()[:16]

    v1_data = {
        "version": "1.0",
        "salt": salt.hex(),
        "key_hash": key_hash,
        "accounts": [],
    }

    path.write_text(json.dumps(v1_data, indent=2), encoding="utf-8")
    path.chmod(0o600)

    vm = VaultManager(str(path))
    try:
        assert vm.unlock(password)
        for acc in accounts:
            assert vm.add_account(acc)
    finally:
        vm.lock()
        vm.close()

    return path.read_bytes()


def _sample_accounts() -> tuple[Account, ...]:
    return (
        Account(
            id="sample_1",
            name="Sample Account 1",
            username="sample1",
            password="sample_password_1",
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest key\n-----END RSA PRIVATE KEY-----",
            private_key_passphrase="test_phrase",
            host="sample1.example.com",
            port=22,
            service_type="ssh",
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
        ),
        Account(
            id="sample_2",
            name="Sample Account 2",
            username="sample2",
            password="sample_password_2",
            private_key=None,
            private_key_passphrase=None,
            host="sample2.example.com",
            port=2222,
            service_type="sftp",
            created_at="2023-01-02T00:00:00Z",
            updated_at="2023-01-02T00:00:00Z",
        ),
    )


class TestVaultUpgradeResult:
    def test_upgrade_result_is_frozen_and_has_contract_fields(self) -> None:
        result = VaultUpgradeResult(
            source_version=1,
            target_version=2,
            accounts_reencrypted=2,
            source_sha256="a" * 64,
            target_sha256="b" * 64,
            backup_deleted=True,
            retained_backup_path=None,
        )

        assert result.source_version == 1
        assert result.target_version == 2
        assert result.accounts_reencrypted == 2
        assert result.source_sha256 == "a" * 64
        assert result.target_sha256 == "b" * 64
        assert result.backup_deleted is True
        assert result.retained_backup_path is None

        with pytest.raises(FrozenInstanceError):
            result.source_version = 3


class TestVaultUpgradeError:
    def test_upgrade_error_exposes_safe_recovery_attributes(self) -> None:
        error = VaultUpgradeError(
            message="Vault upgrade failed",
            rollback_succeeded=False,
            recovery_backup_path="/tmp/fake-backup",
            source_sha256="a" * 64,
            backup_sha256="b" * 64,
        )

        assert str(error) == "Vault upgrade failed"
        assert error.rollback_succeeded is False
        assert error.recovery_backup_path == "/tmp/fake-backup"
        assert error.source_sha256 == "a" * 64
        assert error.backup_sha256 == "b" * 64

        error_str = str(error)
        assert FAKE_PASSWORD not in error_str


class TestSha256File:
    def test_sha256_file_known_bytes(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        result = _sha256_file(test_file)
        assert result == expected_hash


class TestLoadSourceDocument:
    def test_load_source_document_accepts_valid_v1(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.json"
        _write_v1_vault(vault_file, "test_password_123")

        result = _load_source_document(vault_file)
        assert result["version"] == "1.0"
        assert "salt" in result
        assert "key_hash" in result
        assert result["accounts"] == []

    @pytest.mark.parametrize("case", [
        "missing",
        "directory",
        "symlink",
        "fifo",
    ])
    def test_load_source_document_rejects_non_regular_sources(
        self, tmp_path: Path, case: str
    ) -> None:
        if case == "missing":
            path = tmp_path / "missing.json"
        elif case == "directory":
            path = tmp_path
        elif case == "symlink":
            symlink_file = tmp_path / "symlink.json"
            symlink_file.symlink_to("/nonexistent/file.json")
            path = symlink_file
        elif case == "fifo":
            fifo_file = tmp_path / "fifo"
            os.mkfifo(str(fifo_file))
            path = fifo_file

        with pytest.raises(VaultUpgradeError) as exc_info:
            _load_source_document(path)

        assert FAKE_PASSWORD not in str(exc_info.value)

    def test_load_source_document_rejects_corrupt_json(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "corrupt.json"
        vault_file.write_text("{ invalid json }", encoding="utf-8")

        with pytest.raises(VaultUpgradeError):
            _load_source_document(vault_file)

    def test_load_source_document_rejects_non_object_json(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "array.json"
        vault_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        with pytest.raises(VaultUpgradeError):
            _load_source_document(vault_file)

    def test_load_source_document_rejects_v2_vault(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.json"
        vm = VaultManager(str(vault_file))
        try:
            assert vm.setup_master_password("test_password_123")
        finally:
            vm.close()

        with pytest.raises(VaultUpgradeError):
            _load_source_document(vault_file)

    def test_load_source_document_rejects_unknown_version(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.json"
        data = {
            "version": 99,
            "salt": "a" * 32,
            "key_hash": "b" * 16,
            "accounts": [],
        }
        vault_file.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(VaultUpgradeError):
            _load_source_document(vault_file)


class TestValidateRawAccounts:
    def test_validate_raw_accounts_returns_ids_for_valid_document(self) -> None:
        document = {
            "accounts": [
                {
                    "id": "account_1",
                    "name": "Test Account 1",
                    "username": "user1",
                    "password": "pass1",
                    "host": "localhost",
                    "port": 22,
                    "service_type": "ssh",
                },
                {
                    "id": "account_2",
                    "name": "Test Account 2",
                    "username": "user2",
                    "host": "example.com",
                    "port": 2222,
                    "service_type": "sftp",
                },
            ],
        }

        result = _validate_raw_accounts(document)
        assert result == ("account_1", "account_2")

    @pytest.mark.parametrize("accounts", [
        pytest.param("not a list", id="non_list"),
        pytest.param(["not a dict", {"id": "account_1"}], id="entry_non_dict"),
        pytest.param([{"name": "Test Account", "username": "user1"}], id="missing_id"),
        pytest.param([{"id": "", "name": "Test Account", "username": "user1"}], id="empty_id"),
        pytest.param([{"id": 123, "name": "Test Account", "username": "user1"}], id="nonstring_id"),
        pytest.param([
            {"id": "duplicate_id", "name": "Account 1", "username": "user1"},
            {"id": "duplicate_id", "name": "Account 2", "username": "user2"},
        ], id="duplicate_id"),
        pytest.param([{
            "id": "test_id",
            "name": "Test Account",
            "username": "user1",
            "unknown_field": "should fail",
        }], id="unknown_field"),
    ])
    def test_validate_raw_accounts_rejects_invalid_documents(
        self, accounts: object
    ) -> None:
        if isinstance(accounts, str):
            document = {"accounts": accounts}
        else:
            document = {"accounts": accounts}

        with pytest.raises(VaultUpgradeError):
            _validate_raw_accounts(document)


class TestCreateSecureBackup:
    """Tests for _create_secure_backup."""

    def test_create_secure_backup_copies_raw_bytes_hash_and_mode(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        backup_path = None
        try:
            backup = _create_secure_backup(vault_file)
            assert isinstance(backup, _BackupInfo)
            assert backup.path.parent == vault_file.parent
            assert backup.path != vault_file
            assert backup.path.exists()
            assert backup.path.read_bytes() == source_bytes
            assert backup.sha256 == hashlib.sha256(source_bytes).hexdigest()
            assert _sha256_file(backup.path) == backup.sha256
            assert stat.S_IMODE(backup.path.stat().st_mode) == 0o600
            backup_path = backup.path
        finally:
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)

    def test_backup_integrity_error_is_not_shadowed_by_cleanup_failure(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """_create_secure_backup integrity VaultUpgradeError is not
        shadowed by an OSError raised during backup-file cleanup."""
        vault_file = tmp_path / "vault.json"
        _write_v1_vault(vault_file, FAKE_PASSWORD)

        # Monkeypatch _sha256_file so source returns one digest and the
        # backup path returns a different digest, forcing the integrity
        # check to raise VaultUpgradeError("Vault backup integrity check
        # failed").
        source_digest = "a" * 64
        backup_digest = "b" * 64

        def selective_sha256(path: Path) -> str:
            if path == vault_file:
                return source_digest
            return backup_digest

        monkeypatch.setattr(
            vault_upgrade_module, "_sha256_file", selective_sha256
        )

        # Monkeypatch Path.unlink to raise OSError for .v1-backup- paths,
        # simulating a cleanup failure that would shadow the integrity error.
        original_unlink = Path.unlink

        def selective_failing_unlink(
            self: Path, *args: object, **kwargs: object
        ) -> None:
            if ".v1-backup-" in str(self):
                raise OSError("Simulated cleanup failure")
            return original_unlink(self, *args, **kwargs)  # type: ignore[call-arg]

        monkeypatch.setattr(Path, "unlink", selective_failing_unlink)

        try:
            with pytest.raises(VaultUpgradeError) as exc_info:
                _create_secure_backup(vault_file)

            error_str = str(exc_info.value)
            assert "integrity" in error_str.lower()
            assert FAKE_PASSWORD not in error_str
        finally:
            # Remove leaked backup temp files using original (unpatched)
            # Path.unlink so the cleanup bypasses the monkeypatch.
            for p in tmp_path.glob(f".{vault_file.name}.v1-backup-*"):
                try:
                    original_unlink(p, missing_ok=True)  # type: ignore[call-arg]
                except Exception:
                    pass


class TestSnapshotV1Accounts:
    """Tests for _snapshot_v1_accounts."""

    def test_snapshot_v1_accounts_preserves_every_field(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        source_doc = _load_source_document(vault_file)
        ids = _validate_raw_accounts(source_doc)
        result = _snapshot_v1_accounts(vault_file, FAKE_PASSWORD, ids)

        expected = [asdict(a) for a in accounts]
        actual = [asdict(a) for a in result]
        assert actual == expected
        assert vault_file.read_bytes() == source_bytes

    def test_snapshot_v1_accounts_rejects_wrong_password_without_mutation(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        source_doc = _load_source_document(vault_file)
        ids = _validate_raw_accounts(source_doc)

        with pytest.raises(VaultUpgradeError) as exc_info:
            _snapshot_v1_accounts(vault_file, "wrong_password", ids)

        error_str = str(exc_info.value)
        assert FAKE_PASSWORD not in error_str
        assert "sample_password_1" not in error_str
        assert vault_file.read_bytes() == source_bytes

    def test_snapshot_v1_accounts_rejects_decryption_or_count_mismatch(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        # Mutate the first encrypted password to a value that will
        # fail AES-GCM decryption while keeping account IDs valid.
        raw = json.loads(vault_file.read_text(encoding="utf-8"))
        raw["accounts"][0]["password"] = "00:00"
        vault_file.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        source_doc = _load_source_document(vault_file)
        ids = _validate_raw_accounts(source_doc)

        with pytest.raises(VaultUpgradeError) as exc_info:
            _snapshot_v1_accounts(vault_file, FAKE_PASSWORD, ids)

        assert "sample_password_1" not in str(exc_info.value)

    def test_snapshot_v1_accounts_rejects_expected_id_mismatch(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        # Pass IDs in reverse order for a deterministic mismatch.
        bad_ids = ("sample_2", "sample_1")

        with pytest.raises(VaultUpgradeError):
            _snapshot_v1_accounts(vault_file, FAKE_PASSWORD, bad_ids)


class TestBuildAndVerifyCandidate:
    """Tests for _account_map, _build_v2_candidate, _verify_v2_accounts."""

    def test_account_map_preserves_every_account_field(self) -> None:
        accounts = _sample_accounts()
        source_ids = tuple(a.id for a in accounts)
        mapped = _account_map(source_ids, accounts)
        assert set(mapped.keys()) == set(source_ids)
        for account in accounts:
            assert asdict(mapped[account.id]) == asdict(account)

    def test_build_and_verify_v2_candidate_preserves_accounts(
        self, tmp_path: Path
    ) -> None:
        accounts = _sample_accounts()
        vault_file = tmp_path / "vault.json"
        _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        # Load/validate/snapshot using existing helpers.
        source_doc = _load_source_document(vault_file)
        ids = _validate_raw_accounts(source_doc)
        snapshot = _snapshot_v1_accounts(vault_file, FAKE_PASSWORD, ids)

        # Capture source JSON encrypted account values.
        source_raw = json.loads(vault_file.read_text(encoding="utf-8"))
        source_encrypted: dict[str, dict[str, object]] = {
            entry["id"]: {
                field: entry.get(field)
                for field in ("password", "private_key", "private_key_passphrase")
            }
            for entry in source_raw["accounts"]
        }

        candidate: Path | None = None
        try:
            candidate = _build_v2_candidate(
                vault_file.parent, FAKE_PASSWORD, snapshot
            )

            # Assert candidate properties.
            assert candidate.exists()
            assert candidate != vault_file
            assert candidate.parent == vault_file.parent
            assert stat.S_IMODE(candidate.stat().st_mode) == 0o600

            # Check document structure.
            candidate_raw = json.loads(
                candidate.read_text(encoding="utf-8")
            )
            assert candidate_raw["version"] == 2
            assert candidate_raw["kdf"] == "argon2id"
            assert isinstance(candidate_raw["accounts"], list)
            assert len(candidate_raw["accounts"]) == len(accounts)

            # No plaintext secrets in candidate text.
            candidate_text = candidate.read_text(encoding="utf-8")
            assert "sample_password_1" not in candidate_text
            assert "sample_password_2" not in candidate_text
            assert "BEGIN RSA PRIVATE KEY" not in candidate_text
            assert "test_phrase" not in candidate_text

            # Encrypted values differ between source and candidate.
            candidate_by_id = {
                entry["id"]: entry for entry in candidate_raw["accounts"]
            }
            for acct in accounts:
                acct_id = acct.id
                for field in (
                    "password",
                    "private_key",
                    "private_key_passphrase",
                ):
                    plaintext_val = getattr(acct, field)
                    if plaintext_val:
                        source_enc_val = source_encrypted[acct_id].get(field)
                        cand_enc_val = candidate_by_id[acct_id].get(field)
                        assert source_enc_val is not None
                        assert cand_enc_val is not None
                        assert source_enc_val != cand_enc_val

            # Verify returns correct hash.
            assert (
                _verify_v2_accounts(candidate, FAKE_PASSWORD, snapshot)
                == _sha256_file(candidate)
            )

            # Fresh VaultManager unlock and verify accounts.
            vm = VaultManager(str(candidate))
            try:
                assert vm.unlock(FAKE_PASSWORD)
                actual_accounts = vm.get_all_accounts()
                assert [asdict(a) for a in actual_accounts] == [
                    asdict(a) for a in accounts
                ]
            finally:
                vm.lock()
                vm.close()
        finally:
            if candidate is not None:
                candidate.unlink(missing_ok=True)

    def test_build_and_verify_empty_candidate(
        self, tmp_path: Path
    ) -> None:
        candidate: Path | None = None
        try:
            candidate = _build_v2_candidate(tmp_path, FAKE_PASSWORD, ())
            assert candidate.exists()

            candidate_raw = json.loads(
                candidate.read_text(encoding="utf-8")
            )
            assert candidate_raw["accounts"] == []

            assert (
                _verify_v2_accounts(candidate, FAKE_PASSWORD, ())
                == _sha256_file(candidate)
            )
        finally:
            if candidate is not None:
                candidate.unlink(missing_ok=True)

    def test_verify_v2_accounts_rejects_field_mismatch(
        self, tmp_path: Path
    ) -> None:
        accounts = _sample_accounts()
        candidate: Path | None = None
        try:
            candidate = _build_v2_candidate(
                tmp_path, FAKE_PASSWORD, accounts
            )

            # Create altered expected Account (same ID, different username).
            altered_dict = asdict(accounts[0])
            altered_dict["username"] = "different_username"
            altered = Account(**altered_dict)
            altered_snapshot = (altered,) + accounts[1:]

            with pytest.raises(VaultUpgradeError):
                _verify_v2_accounts(
                    candidate, FAKE_PASSWORD, altered_snapshot
                )
        finally:
            if candidate is not None:
                candidate.unlink(missing_ok=True)

    def test_build_v2_candidate_cleans_up_when_setup_fails(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            VaultManager,
            "setup_master_password",
            lambda self, pw: False,
        )

        before = set(tmp_path.glob(".vault-v2-candidate-*"))

        with pytest.raises(VaultUpgradeError):
            _build_v2_candidate(
                tmp_path, FAKE_PASSWORD, _sample_accounts()
            )

        after = set(tmp_path.glob(".vault-v2-candidate-*"))
        assert after == before

    def test_build_v2_candidate_cleans_up_when_add_fails(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            VaultManager,
            "add_account",
            lambda self, account: False,
        )

        before = set(tmp_path.glob(".vault-v2-candidate-*"))

        with pytest.raises(VaultUpgradeError):
            _build_v2_candidate(
                tmp_path, FAKE_PASSWORD, _sample_accounts()
            )

        after = set(tmp_path.glob(".vault-v2-candidate-*"))
        assert after == before

    def test_build_v2_candidate_unlocks_before_add(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        events: list[str] = []

        original_setup = VaultManager.setup_master_password
        original_unlock = VaultManager.unlock
        original_add = VaultManager.add_account

        def recording_setup(
            self: VaultManager, pw: str
        ) -> bool:
            events.append("setup")
            return original_setup(self, pw)

        def recording_unlock(
            self: VaultManager, pw: str
        ) -> bool:
            events.append("unlock")
            return original_unlock(self, pw)

        def recording_add(
            self: VaultManager, account: Account
        ) -> bool:
            events.append(f"add:{account.id}")
            return original_add(self, account)

        monkeypatch.setattr(
            VaultManager, "setup_master_password", recording_setup
        )
        monkeypatch.setattr(
            VaultManager, "unlock", recording_unlock
        )
        monkeypatch.setattr(
            VaultManager, "add_account", recording_add
        )

        accounts = _sample_accounts()
        candidate: Path | None = None
        try:
            candidate = _build_v2_candidate(
                tmp_path, FAKE_PASSWORD, accounts
            )

            assert events[0] == "setup"
            assert events[1] == "unlock"
            for i, acct in enumerate(accounts):
                assert events[2 + i] == f"add:{acct.id}"
        finally:
            if candidate is not None:
                candidate.unlink(missing_ok=True)

    def test_build_v2_candidate_rejects_non_account_safely(
        self, tmp_path: Path
    ) -> None:
        before = set(tmp_path.glob(".vault-v2-candidate-*"))

        with pytest.raises(VaultUpgradeError):
            _build_v2_candidate(
                tmp_path, FAKE_PASSWORD, (object(),)  # type: ignore[arg-type]
            )

        after = set(tmp_path.glob(".vault-v2-candidate-*"))
        assert after == before

    def test_verify_v2_accounts_rejects_valid_v1_vault(
        self, tmp_path: Path
    ) -> None:
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        source_doc = _load_source_document(vault_file)
        ids = _validate_raw_accounts(source_doc)
        snapshot = _snapshot_v1_accounts(vault_file, FAKE_PASSWORD, ids)

        with pytest.raises(VaultUpgradeError):
            _verify_v2_accounts(vault_file, FAKE_PASSWORD, snapshot)

        assert vault_file.read_bytes() == source_bytes


class TestUpgradeVaultV1ToV2Success:
    """Success-path tests for upgrade_vault_v1_to_v2."""

    def test_multi_account_success(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Upgrade a v1 vault with multiple accounts to v2 successfully."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        # Spy on os.replace in vault_upgrade module (shared os module:
        # wrapper always calls captured original).
        original_replace = os.replace
        replace_calls: list[tuple[str, str]] = []

        def recording_replace(*args: object, **kwargs: object) -> object:
            if len(args) >= 2 and str(args[1]) == str(vault_file):
                replace_calls.append((str(args[0]), str(args[1])))
            return original_replace(*args, **kwargs)

        monkeypatch.setattr(
            "openadmindesk.core.vault_upgrade.os.replace",
            recording_replace,
        )

        result = upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        # Assert result is VaultUpgradeResult with expected fields.
        assert isinstance(result, VaultUpgradeResult)
        assert result.source_version == 1
        assert result.target_version == 2
        assert result.accounts_reencrypted == 2
        assert result.source_sha256 == initial_hash
        assert result.target_sha256 == _sha256_file(vault_file)
        assert result.backup_deleted is True
        assert result.retained_backup_path is None

        # Exactly one os.replace into source path with candidate src.
        assert len(replace_calls) == 1
        replaced_src = replace_calls[0][0]
        assert ".vault-v2-candidate-" in replaced_src

        # Source bytes changed (v2 replaces v1).
        final_bytes = vault_file.read_bytes()
        assert final_bytes != source_bytes

        # Final document is valid v2 argon2id.
        final_raw = json.loads(vault_file.read_text(encoding="utf-8"))
        assert final_raw["version"] == 2
        assert final_raw["kdf"] == "argon2id"

        # Mode is owner-only.
        assert stat.S_IMODE(vault_file.stat().st_mode) == 0o600

        # Fresh VaultManager unlocks and yields every account
        # asdict/order matching originals.
        vm = VaultManager(str(vault_file))
        try:
            assert vm.unlock(FAKE_PASSWORD)
            actual_accounts = vm.get_all_accounts()
            assert [asdict(a) for a in actual_accounts] == [
                asdict(a) for a in accounts
            ]
        finally:
            vm.lock()
            vm.close()

        # No leftover candidate or backup files.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []
        assert list(tmp_path.glob(f".{vault_file.name}.v1-backup-*")) == []

        # No plaintext secrets in final JSON.
        vault_text = vault_file.read_text(encoding="utf-8")
        assert "sample_password_1" not in vault_text
        assert "sample_password_2" not in vault_text
        assert "BEGIN RSA PRIVATE KEY" not in vault_text
        assert "test_phrase" not in vault_text

    def test_empty_vault_success(
        self, tmp_path: Path
    ) -> None:
        """Upgrade an empty v1 vault to v2 successfully."""
        vault_file = tmp_path / "vault.json"
        _write_v1_vault(vault_file, FAKE_PASSWORD)
        initial_hash = hashlib.sha256(
            vault_file.read_bytes()
        ).hexdigest()

        result = upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        assert isinstance(result, VaultUpgradeResult)
        assert result.source_version == 1
        assert result.target_version == 2
        assert result.accounts_reencrypted == 0
        assert result.source_sha256 == initial_hash
        assert result.target_sha256 == _sha256_file(vault_file)
        assert result.backup_deleted is True
        assert result.retained_backup_path is None

        # Final v2 document has empty accounts list.
        final_raw = json.loads(vault_file.read_text(encoding="utf-8"))
        assert final_raw["version"] == 2
        assert final_raw["kdf"] == "argon2id"
        assert final_raw["accounts"] == []

        # Fresh VaultManager unlock with same password yields [].
        vm = VaultManager(str(vault_file))
        try:
            assert vm.unlock(FAKE_PASSWORD)
            assert vm.get_all_accounts() == []
        finally:
            vm.lock()
            vm.close()

        # No candidate or backup residue.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []
        assert list(tmp_path.glob(f".{vault_file.name}.v1-backup-*")) == []


class TestUpgradeVaultV1ToV2Failures:
    """Fault-injection tests for upgrade_vault_v1_to_v2 failure paths."""

    def test_wrong_password_preserves_source_and_safe_error(
        self, tmp_path: Path
    ) -> None:
        """Wrong master password: original bytes unchanged, no
        candidate/backup, secret-safe error."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, "wrong_password")

        error = exc_info.value

        # Source file is completely unchanged.
        assert vault_file.read_bytes() == source_bytes

        # No candidate or backup was created.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []
        assert list(tmp_path.glob(f".{vault_file.name}.v1-backup-*")) == []

        # Error metadata.
        assert error.rollback_succeeded is None
        assert error.recovery_backup_path is None
        assert error.source_sha256 == initial_hash

        # No secrets in the error string.
        error_str = str(error)
        assert "password is invalid or data is unreadable" in error_str
        assert FAKE_PASSWORD not in error_str
        assert "sample_password_1" not in error_str
        assert "sample_password_2" not in error_str
        assert "BEGIN RSA PRIVATE KEY" not in error_str

    def test_candidate_build_failure_after_backup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """_build_v2_candidate raises after backup succeeded: source
        unchanged, exactly one retained backup, safe error."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        def failing_build(
            directory: Path,
            master_password: str,
            accts: tuple[Account, ...],
        ) -> Path:
            raise VaultUpgradeError("Candidate build failed")

        monkeypatch.setattr(
            vault_upgrade_module,
            "_build_v2_candidate",
            failing_build,
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Source file is completely unchanged.
        assert vault_file.read_bytes() == source_bytes

        # No candidate file was created.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # Exactly one backup was retained with raw original bytes / mode.
        backups = sorted(
            tmp_path.glob(f".{vault_file.name}.v1-backup-*")
        )
        assert len(backups) == 1
        retained_backup = backups[0]
        assert retained_backup.read_bytes() == source_bytes
        assert stat.S_IMODE(retained_backup.stat().st_mode) == 0o600

        # Error metadata.
        assert error.rollback_succeeded is None
        assert error.recovery_backup_path == str(retained_backup)
        assert error.source_sha256 == initial_hash
        assert error.backup_sha256 == hashlib.sha256(source_bytes).hexdigest()

        # No secrets in the error string.
        error_str = str(error)
        assert FAKE_PASSWORD not in error_str
        assert "sample_password_1" not in error_str
        assert "sample_password_2" not in error_str

        # Cleanup.
        retained_backup.unlink()

    def test_source_changes_before_replace(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """External source modification after candidate verification:
        source reflects external change, candidate cleaned, backup
        retained, rollback is None."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        original_verify = vault_upgrade_module._verify_v2_accounts

        def verify_then_mutate_source(
            path: Path,
            master_password: str,
            expected: tuple[Account, ...],
        ) -> str:
            result = original_verify(path, master_password, expected)
            # After successful candidate verification (path is the
            # candidate, not vault_file) modify the source exactly once.
            if path != vault_file:
                vault_file.write_bytes(vault_file.read_bytes() + b"\n")
            return result

        monkeypatch.setattr(
            vault_upgrade_module,
            "_verify_v2_accounts",
            verify_then_mutate_source,
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Source bytes reflect the external change (original + b"\\n").
        assert vault_file.read_bytes() == source_bytes + b"\n"

        # No leftover candidate.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # Backup retained with raw original bytes.
        backups = sorted(
            tmp_path.glob(f".{vault_file.name}.v1-backup-*")
        )
        assert len(backups) == 1
        retained_backup = backups[0]
        assert retained_backup.read_bytes() == source_bytes

        # rollback is None (source was never replaced).
        assert error.rollback_succeeded is None

        # Cleanup.
        retained_backup.unlink()

    def test_source_target_os_replace_failure(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """os.replace raises OSError: source exact original, candidate
        cleaned up, backup retained, rollback None."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)

        original_replace = os.replace

        def failing_replace(src: str, dst: str) -> None:
            if (
                str(dst) == str(vault_file)
                and ".vault-v2-candidate-" in str(src)
            ):
                raise OSError("Permission denied")
            return original_replace(src, dst)

        monkeypatch.setattr(
            vault_upgrade_module.os,
            "replace",
            failing_replace,
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Source file unchanged (os.replace never completed).
        assert vault_file.read_bytes() == source_bytes

        # Candidate file cleaned up by exception handler.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # Back-up retained with raw original bytes.
        backups = sorted(
            tmp_path.glob(f".{vault_file.name}.v1-backup-*")
        )
        assert len(backups) == 1
        retained_backup = backups[0]
        assert retained_backup.read_bytes() == source_bytes

        # rollback is None (source was never replaced).
        assert error.rollback_succeeded is None

        # Cleanup.
        retained_backup.unlink()


class TestInspectVaultVersion:
    def test_inspect_v1_returns_1(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.json"
        _write_v1_vault(vault_file, "test_password")
        assert inspect_vault_version(vault_file) == 1

    def test_inspect_v2_returns_2(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.json"
        from openadmindesk.core.vault_manager import VaultManager
        vm = VaultManager(str(vault_file))
        try:
            assert vm.setup_master_password("test_password")
        finally:
            vm.close()
        assert inspect_vault_version(vault_file) == 2

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

    def test_inspect_rejects_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "vault.json"
        path.write_text("{ invalid json }", encoding="utf-8")
        with pytest.raises(VaultUpgradeError):
            inspect_vault_version(path)

    def test_inspect_rejects_non_object(self, tmp_path: Path) -> None:
        path = tmp_path / "vault.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(VaultUpgradeError):
            inspect_vault_version(path)

    def test_inspect_rejects_unknown_version(self, tmp_path: Path) -> None:
        path = tmp_path / "vault.json"
        path.write_text(json.dumps({"version": 99}), encoding="utf-8")
        with pytest.raises(VaultUpgradeError):
            inspect_vault_version(path)

    def test_inspect_rejects_structurally_invalid_v1(self, tmp_path: Path) -> None:
        path = tmp_path / "vault.json"
        path.write_text(json.dumps({"version": "1.0", "salt": "a" * 32}), encoding="utf-8")
        with pytest.raises(VaultUpgradeError):
            inspect_vault_version(path)

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


class TestUpgradeVaultV1ToV2RollbackAndCleanup:
    """Fault-injection tests for backup cleanup and rollback behaviour."""

    def test_backup_deletion_failure_is_successful_upgrade(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Path.unlink fails for backup file: upgrade still succeeds,
        result.backup_deleted is False, retained backup exists with
        original bytes/mode; final source is valid v2."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        original_unlink = Path.unlink

        def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
            if ".v1-backup-" in str(self):
                raise OSError("Backup deletion failed")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", failing_unlink)

        result = upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        assert result.backup_deleted is False
        assert result.retained_backup_path is not None

        retained_backup = Path(result.retained_backup_path)
        assert retained_backup.exists()
        assert retained_backup.read_bytes() == source_bytes
        assert stat.S_IMODE(retained_backup.stat().st_mode) == 0o600

        # Final source is a valid v2 vault.
        final_raw = json.loads(vault_file.read_text(encoding="utf-8"))
        assert final_raw["version"] == 2
        assert final_raw["kdf"] == "argon2id"

        # Same password unlocks and accounts match.
        vm = VaultManager(str(vault_file))
        try:
            assert vm.unlock(FAKE_PASSWORD)
            actual_accounts = vm.get_all_accounts()
            assert [asdict(a) for a in actual_accounts] == [
                asdict(a) for a in accounts
            ]
        finally:
            vm.lock()
            vm.close()

        # No leftover candidate.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # Cleanup: use captured original unlink (Path.unlink is still
        # monkeypatched).
        original_unlink(retained_backup)

    def test_installed_verification_failure_rolls_back(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """_verify_v2_accounts passes for the candidate but raises after
        replacement: rollback restores original v1 source, backup
        retained, no candidate or rollback temp file."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        original_verify = vault_upgrade_module._verify_v2_accounts

        def post_replace_raising_verify(
            path: Path,
            master_password: str,
            expected: tuple[Account, ...],
        ) -> str:
            result = original_verify(path, master_password, expected)
            # Raise only when called for the installed vault file
            # (post-replacement).
            if path == vault_file:
                raise VaultUpgradeError(
                    "Installed verification failed",
                )
            return result

        monkeypatch.setattr(
            vault_upgrade_module,
            "_verify_v2_accounts",
            post_replace_raising_verify,
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Rollback succeeded.
        assert error.rollback_succeeded is True
        assert error.recovery_backup_path is not None

        recovery_path = Path(error.recovery_backup_path)
        assert recovery_path.exists()
        assert recovery_path.read_bytes() == source_bytes
        assert error.source_sha256 == initial_hash
        assert error.backup_sha256 == hashlib.sha256(source_bytes).hexdigest()

        # Source bytes were restored to the original v1 content.
        assert vault_file.read_bytes() == source_bytes

        # Original v1 unlocks with same password and accounts.
        vm = VaultManager(str(vault_file))
        try:
            assert vm.unlock(FAKE_PASSWORD)
            actual_accounts = vm.get_all_accounts()
            assert [asdict(a) for a in actual_accounts] == [
                asdict(a) for a in accounts
            ]
        finally:
            vm.lock()
            vm.close()

        # No leftover candidate.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # No .v1-rollback-* temp file.
        assert list(tmp_path.glob(f".{vault_file.name}.v1-rollback-*")) == []

        # Cleanup retained backup.
        recovery_path.unlink(missing_ok=True)

    def test_rollback_failure_is_explicit(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Installed verification failure plus _restore_v1_backup
        returning False: rollback_succeeded is False, backup retained,
        source version is uncertain."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        original_verify = vault_upgrade_module._verify_v2_accounts

        def post_replace_raising_verify(
            path: Path,
            master_password: str,
            expected: tuple[Account, ...],
        ) -> str:
            result = original_verify(path, master_password, expected)
            if path == vault_file:
                raise VaultUpgradeError(
                    "Installed verification failed",
                )
            return result

        monkeypatch.setattr(
            vault_upgrade_module,
            "_verify_v2_accounts",
            post_replace_raising_verify,
        )

        # Simulate a rollback implementation that fails to restore.
        def failing_restore(
            backup_path: Path,
            target_path: Path,
        ) -> bool:
            return False

        monkeypatch.setattr(
            vault_upgrade_module,
            "_restore_v1_backup",
            failing_restore,
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Rollback was attempted but failed.
        assert error.rollback_succeeded is False
        assert error.recovery_backup_path is not None

        recovery_path = Path(error.recovery_backup_path)
        assert recovery_path.exists()
        assert recovery_path.read_bytes() == source_bytes
        assert error.source_sha256 == initial_hash
        assert error.backup_sha256 == hashlib.sha256(source_bytes).hexdigest()

        # No leftover candidate.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []

        # Source version is intentionally not asserted because the
        # recovery state is uncertain after failed rollback.

        # Cleanup.
        recovery_path.unlink(missing_ok=True)

    def test_insecure_installed_mode_triggers_rollback(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When the installed v2 replacement has insecure permissions
        (0644), the upgrade rolls back to the original v1 source with
        mode 0600.  The rollback path itself is not re-chmodded."""
        vault_file = tmp_path / "vault.json"
        accounts = _sample_accounts()
        source_bytes = _write_v1_vault(vault_file, FAKE_PASSWORD, accounts)
        initial_hash = hashlib.sha256(source_bytes).hexdigest()

        original_replace = os.replace

        def mode_attacking_replace(src: str, dst: str) -> None:
            # Always call the real os.replace first.
            original_replace(src, dst)
            # After the v2 candidate is installed at vault_file, change
            # the mode to 0644 (insecure).  Never chmod during rollback
            # (which uses .v1-rollback-* sources).
            if ".vault-v2-candidate-" in str(src) and str(dst) == str(vault_file):
                os.chmod(dst, 0o644)

        monkeypatch.setattr(
            vault_upgrade_module.os, "replace", mode_attacking_replace
        )

        with pytest.raises(VaultUpgradeError) as exc_info:
            upgrade_vault_v1_to_v2(vault_file, FAKE_PASSWORD)

        error = exc_info.value

        # Rollback status and backup were preserved.
        assert error.rollback_succeeded is True
        assert error.recovery_backup_path is not None

        recovery_path = Path(error.recovery_backup_path)
        assert recovery_path.exists()
        assert recovery_path.read_bytes() == source_bytes
        assert error.source_sha256 == initial_hash
        assert error.backup_sha256 == hashlib.sha256(source_bytes).hexdigest()

        # Source file was restored to the original v1 content with
        # owner-only mode.
        assert vault_file.read_bytes() == source_bytes
        assert stat.S_IMODE(vault_file.stat().st_mode) == 0o600

        # No leftover candidate or rollback temp file.
        assert list(tmp_path.glob(".vault-v2-candidate-*")) == []
        assert list(tmp_path.glob(f".{vault_file.name}.v1-rollback-*")) == []

        # Cleanup retained backup.
        recovery_path.unlink(missing_ok=True)
