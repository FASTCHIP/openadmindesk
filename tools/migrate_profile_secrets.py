#!/usr/bin/env python3
"""Migrate legacy plaintext profile secrets into an unlocked vault."""

from __future__ import annotations

import argparse
import json
import os
import sys

from openadmindesk.core.profile_secret_migration import (
    ProfileSecretMigrationResult,
    ProfileSecretScanReport,
    migrate_plaintext_profile_secrets,
    scan_plaintext_profile_secrets,
)
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.platform.platform_utils import default_db_path, default_vault_path


def _print_text_report(report: ProfileSecretScanReport) -> None:
    """Print dry-run scan report in human-readable text format."""
    print(f"Total profiles: {report.total_profiles}")
    print(f"Affected profiles: {report.affected_profiles}")
    print(f"  Primary credentials only: {report.primary_only}")
    print(f"  Gateway credentials only: {report.gateway_only}")
    print(f"  Mixed (primary + gateway): {report.mixed}")
    print("\nProfiles with plaintext secrets:")
    for profile in report.profiles:
        print(f"  {profile.name}:")
        print(f"    Primary: password={profile.has_password}, passphrase={profile.has_passphrase}")
        print(f"    Gateway: password={profile.has_gateway_password}")
        print(
            f"    Already migrated: credential_id={profile.has_credential_id}, "
            f"gateway_credential_id={profile.has_gateway_credential_id}"
        )


def _print_json_report(report: ProfileSecretScanReport) -> None:
    """Print dry-run scan report as structured JSON."""
    report_dict = {
        "total_profiles": report.total_profiles,
        "affected_profiles": report.affected_profiles,
        "primary_only": report.primary_only,
        "gateway_only": report.gateway_only,
        "mixed": report.mixed,
        "profiles": [
            {
                "name": p.name,
                "has_password": p.has_password,
                "has_passphrase": p.has_passphrase,
                "has_gateway_password": p.has_gateway_password,
                "has_credential_id": p.has_credential_id,
                "has_gateway_credential_id": p.has_gateway_credential_id,
            }
            for p in report.profiles
        ],
    }
    print(json.dumps(report_dict, indent=2))


def _print_text_result(result: ProfileSecretMigrationResult) -> None:
    """Print migration result in human-readable text format."""
    print(f"Scanned profiles: {result.scanned}")
    print(f"Primary secrets migrated: {result.primary_migrated}")
    print(f"Gateway secrets migrated: {result.gateway_migrated}")
    print(f"Primary secrets cleared (already matched): {result.primary_cleared}")
    print(f"Gateway secrets cleared (already matched): {result.gateway_cleared}")
    print(f"Total migrated (compatibility): {result.migrated}")
    print(f"Total cleared only (compatibility): {result.cleared_only}")
    if result.backup:
        print(f"\nBackup database: {result.backup.db_backup_path}")
        print(f"  SHA-256: {result.backup.db_sha256}")
        print(f"Backup vault: {result.backup.vault_backup_path}")
        print(f"  SHA-256: {result.backup.vault_sha256}")
    else:
        print("\nNo backup created (no secrets required migration)")


def _print_json_result(result: ProfileSecretMigrationResult) -> None:
    """Print migration result as structured JSON."""
    d: dict = {
        "scanned": result.scanned,
        "primary_migrated": result.primary_migrated,
        "gateway_migrated": result.gateway_migrated,
        "primary_cleared": result.primary_cleared,
        "gateway_cleared": result.gateway_cleared,
        "migrated": result.migrated,
        "cleared_only": result.cleared_only,
    }
    if result.backup:
        d["backup"] = {
            "db_backup_path": result.backup.db_backup_path,
            "vault_backup_path": result.backup.vault_backup_path,
            "db_sha256": result.backup.db_sha256,
            "vault_sha256": result.backup.vault_sha256,
        }
    else:
        d["backup"] = None
    print(json.dumps(d, indent=2))


def main(argv: list[str] | None = None) -> int:
    """Run the profile-secret migration tool."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=default_db_path(),
        help="Path to profile database (default: platform data dir)",
    )
    parser.add_argument(
        "--vault",
        default=default_vault_path(),
        help="Path to encrypted vault (default: platform data dir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan only; do not migrate or touch vault",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (applies to dry-run and migration result)",
    )
    parser.add_argument(
        "--password-env",
        default="OPENADMINDESK_VAULT_PASSWORD",
        help="Environment variable holding the vault master password",
    )
    parser.add_argument(
        "--confirm-cleartext-removal",
        action="store_true",
        help="Acknowledge that cleartext secrets will be removed from the database",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Target directory for pre-migration backups (default: <db_parent>/backups)",
    )
    args = parser.parse_args(argv)

    # ── Dry-run: vault never instantiated, env never read ──────────────
    if args.dry_run:
        report = scan_plaintext_profile_secrets(args.db)
        if args.format == "json":
            _print_json_report(report)
        else:
            _print_text_report(report)
        return 0

    # ── Live migration ─────────────────────────────────────────────────

    # Require explicit confirmation before touching vault / env
    if not args.confirm_cleartext_removal:
        print(
            "Error: --confirm-cleartext-removal is required for live migration. "
            "Use --dry-run first to assess which profiles are affected.",
            file=sys.stderr,
        )
        return 2

    # Read password from environment only — no interactive prompt, no CLI arg
    password = os.environ.get(args.password_env)
    if not password:
        print(
            f"Error: environment variable {args.password_env!r} is not set or empty",
            file=sys.stderr,
        )
        return 2

    vault = VaultManager(vault_path=args.vault)
    if not vault.unlock(password):
        print("Error: vault unlock failed (wrong password or corrupt vault)", file=sys.stderr)
        return 1

    try:
        result = migrate_plaintext_profile_secrets(
            args.db,
            vault,
            confirm_cleartext_removal=True,
            backup_dir=args.backup_dir,
        )
    except RuntimeError as exc:
        # exc message may contain profile names and backup paths but never secrets
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        vault.lock()

    if args.format == "json":
        _print_json_result(result)
    else:
        _print_text_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
