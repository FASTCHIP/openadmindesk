#!/usr/bin/env python3
"""Migrate legacy plaintext profile secrets into an unlocked vault."""

from __future__ import annotations

import argparse
import json
import sys

from openadmindesk.core.profile_secret_migration import scan_plaintext_profile_secrets
from openadmindesk.platform.platform_utils import default_db_path


def _print_text_report(report):
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
        print(f"    Already migrated: credential_id={profile.has_credential_id}, gateway_credential_id={profile.has_gateway_credential_id}")


def _print_json_report(report):
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for dry-run",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        # Dry-run mode: no vault unlock, no mutation, just reporting
        report = scan_plaintext_profile_secrets(args.db)
        if args.format == "text":
            _print_text_report(report)
        else:
            _print_json_report(report)
        return 0

    # Non-dry-run: fail closed immediately before any vault interaction
    print("live migration is disabled; use --dry-run for assessment", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
