# Security Model

## Goals

- Keep secrets encrypted at rest.
- Avoid leaking secrets through logs, crash reports, command lines, or shell
  history.
- Preserve normal OpenSSH security behavior.
- Make destructive actions explicit.

## Credential Vault

The vault is a versioned JSON file (`~/.local/share/openadmindesk/vault.json`)
with per-value AES-256-GCM encryption. Encryption keys are derived from the
master password. The master password must never be stored.

### Versioned KDF reality

**v1 (legacy, readable):** version string `"1.0"`. PBKDF2-HMAC-SHA256 with
100000 iterations (invalid values fall back to 100000), 16-byte salt (32 hex
chars), truncated 8-byte key hash (16 hex chars; SHA-256 first 16 chars). Read,
write, and unlock continue to work.

**v2 (new creation, default):** version integer `2`. Argon2id with default
parameters `time_cost=2`, `memory_cost=19456` KiB, `parallelism=1`,
`hash_len=32`, `version=19`. HMAC-SHA256 password verifier stored as
`password_hash` (64 hex chars). AES-256-GCM with a fresh 12-byte nonce per
sensitive value (`password`, `private_key`, `private_key_passphrase`). Nonce and
ciphertext are stored as `nonce_hex:ciphertext_hex` in the account dictionary.

### v1→v2 vault upgrade

A core API function `upgrade_vault_v1_to_v2(path, master_password)` performs
explicit re-encryption with backup and verified rollback. It is never automatic
on startup.

Sequence:
1. Load, validate version and account structure; hash source.
2. Unlock v1 vault, decrypt all accounts, confirm full decryption.
3. Create a same-directory raw-`0o600` fsynced backup; verify source hash
   matches backup hash.
4. Build a v2 candidate vault (same password, all accounts re-encrypted with
   Argon2id + AES-GCM fresh nonces); verify all accounts decrypt correctly.
5. Hash source again; on mismatch abort (source changed under us).
6. `os.replace` candidate → source (atomic on POSIX).
7. Verify installed vault: all accounts decrypt, hash matches candidate hash.
8. Delete backup on success; if deletion fails, return success with
   `retained_backup_path` set.

**Failure semantics:**

- **Failures before replacement** (steps 1–5): leave the source vault untouched,
  clean up the candidate file, and retain any backup that was already created.
  No rollback is attempted.
- **Failures after replacement** (step 7 installed verification failure):
  attempt a verified rollback from the backup (hash check, `os.replace`,
  mode `0o600` verification). Errors carry secret-safe metadata
  (`source_sha256`, `backup_sha256`, `recovery_backup_path`,
  `rollback_succeeded`).

**No UI or CLI upgrade flow yet** (Phase 9.9d). Callers must ensure exclusive
write access during the upgrade.

## Accounts

Account records contain the following fields:

- `id` — unique identifier string.
- `name` — display name.
- `username` — login username.
- `password` — sensitive; AES-256-GCM encrypted.
- `private_key` — sensitive; AES-256-GCM encrypted.
- `private_key_passphrase` — sensitive; AES-256-GCM encrypted.
- `host` — remote host.
- `port` — remote port.
- `service_type` — service type string.
- `created_at` — ISO-8601 UTC creation timestamp.
- `updated_at` — ISO-8601 UTC last update timestamp.

Host profiles reference accounts by internal ID through `credential_id`.


## Legacy Profile Secret Migration

Existing SQLite databases may contain plaintext values from older builds. This
migration is explicit and never runs on startup:

```bash
OPENADMINDESK_VAULT_PASSWORD=... python3 tools/migrate_profile_secrets.py --confirm-cleartext-removal
```

The migration requires an unlocked vault, moves profile `password` and
`private_key_passphrase` values into vault accounts, writes `credential_id` back
to the profile row, and clears legacy secret columns. RDP gateway passwords are
cleared until the vault account model has a dedicated gateway credential field.

## Logging Rules

Never log:

- master password,
- account password,
- private-key passphrase,
- private key content,
- tokens,
- full command lines containing secrets.

Log safe command structure and non-secret options only.

## SSH Rules

- Do not disable host key checking silently.
- Prefer OpenSSH defaults unless the user explicitly changes behavior.
- Use identity files by path; do not import private key content into the vault in
  the MVP.
- Build subprocess calls with argument arrays.

## Remote File Rules

- Confirm destructive file operations.
- Recursive delete requires a dedicated implementation and tests.
- Show remote paths clearly before destructive actions.
## Proxy And Jump Host Rules

Supported `proxy_command` values are intentionally narrow while the app uses Paramiko:

- `ssh -W %h:%p jump.example.com`
- `nc host port` / `ncat host port`
- `socat ...`
- `connect-proxy ...`

Shell metacharacters, control characters, pipelines, command substitutions, and unsupported binaries are rejected. SSH and tunnel host/user fields are also validated before command construction.

## SSH Host-Key Trust

OpenAdminDesk uses explicit trust-on-first-use for Paramiko SSH/SFTP connections.
Unknown server keys are rejected by default and exposed as a pending fingerprint; the UI can then ask the user to trust the key and retry the connection. Accepted keys are stored in the OpenAdminDesk known-hosts file at `~/.config/openadmindesk/known_hosts`.

The application also loads system host keys before its own store, so existing OS-level trust remains valid. It must not use Paramiko `AutoAddPolicy` or silently continue after a missing host-key event.

## RDP Gateway Secrets

RDP profiles must not persist `rdp_gateway_password` in SQLite or exported profile files. Gateway credentials are stored as a dedicated vault account and referenced through `Profile.rdp_gateway_credential_id`, separate from the primary `credential_id`. Runtime profile copies may hydrate `rdp_gateway_password` only after the vault is unlocked.
