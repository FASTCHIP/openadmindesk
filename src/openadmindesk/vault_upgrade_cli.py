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