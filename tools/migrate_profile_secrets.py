#!/usr/bin/env python3
"""Migrate legacy plaintext profile secrets into an unlocked vault."""

from __future__ import annotations

import argparse
import os

from openadmindesk.core.profile_secret_migration import migrate_plaintext_profile_secrets
from openadmindesk.core.vault_manager import VaultManager
from openadmindesk.platform.platform_utils import default_db_path, default_vault_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--vault", default=default_vault_path())
    parser.add_argument("--password-env", default="OPENADMINDESK_VAULT_PASSWORD")
    parser.add_argument("--confirm-cleartext-removal", action="store_true")
    args = parser.parse_args()

    password = os.environ.get(args.password_env)
    if not password:
        parser.error(f"set {args.password_env} with the vault master password")
    vault = VaultManager(args.vault)
    if not vault.unlock(password):
        raise SystemExit("failed to unlock vault")
    result = migrate_plaintext_profile_secrets(
        args.db,
        vault,
        confirm_cleartext_removal=args.confirm_cleartext_removal,
    )
    print(
        "profile secret migration: "
        f"scanned={result.scanned} migrated={result.migrated} "
        f"cleared_only={result.cleared_only}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
