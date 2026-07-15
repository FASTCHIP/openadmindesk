# Vault Specification

The credential vault stores secrets for accounts. It is separate from
connection profile metadata.

## Goals

- Encrypt secrets at rest.
- Never store the master password.
- Keep account metadata searchable without exposing secrets.
- Make testing possible with fake secrets only.

## Storage

Path:

```text
~/.local/share/openadmindesk/vault.json
```

Format: JSON with version-aware metadata. File permissions are `0o600`
(owner read/write only). Writes use atomic `os.replace` via a same-directory
temporary file.

## Vault Metadata (v1 — legacy, readable)

```json
{
  "version": "1.0",
  "salt": "<32 hex chars (16 bytes)>",
  "key_hash": "<16 hex chars (truncated SHA-256 first 8 bytes)>",
  "iv": "",
  "ciphertext": "",
  "accounts": [],
  "kdf": "pbkdf2-sha256",
  "kdf_params": {"iterations": 100000, "length": 32},
  "created_at": "2026-07-15T12:00:00Z",
  "updated_at": "2026-07-15T12:00:00Z"
}
```

- `version`: string `"1.0"` — `detect_version` returns `1`.
- `salt`: exactly 32 hex chars when non-empty; empty allowed for template.
- `key_hash`: exactly 16 hex chars when non-empty; SHA-256(key)`[:16]` in hex.
- `iv`/`ciphertext`: legacy backward-compatible strings; not used by vault
  (secrets are stored in `accounts[]`).
- `kdf`: optional `"pbkdf2-sha256"`.
- `kdf_params`: optional `{"iterations": 100000, "length": 32}`.
- `created_at` / `updated_at`: optional ISO-8601 UTC strings.

## Vault Metadata (v2 — new creation, default)

```json
{
  "version": 2,
  "salt": "<32 hex chars (16 bytes)>",
  "kdf": "argon2id",
  "kdf_params": {
    "time_cost": 2,
    "memory_cost": 19456,
    "parallelism": 1,
    "hash_len": 32,
    "version": 19
  },
  "password_hash": "<64 hex chars (HMAC-SHA256)>",
  "accounts": [],
  "created_at": "2026-07-15T12:00:00Z",
  "updated_at": "2026-07-15T12:00:00Z"
}
```

- `version`: integer `2` — `detect_version` returns `2`.
- `kdf`: exactly `"argon2id"`.
- `kdf_params`: exact five-key set required; each value must be `int` (not
  `bool`). Defaults: `time_cost=2`, `memory_cost=19456` (KiB),
  `parallelism=1`, `hash_len=32`, `version=19`.
- `password_hash`: HMAC-SHA256(derived_key, `b"openadmindesk-vault-v2-verifier"`)
  as 64 hex chars; empty allowed for template.
- `salt`: exactly 32 hex chars when non-empty.
- No `iv`, `ciphertext`, or `key_hash` fields.

## Account Record (both v1 and v2)

Accounts are stored as JSON objects in the `accounts[]` list. Sensitive fields
are individually encrypted with AES-256-GCM using the vault's derived key.

Account fields stored in plaintext in the account dict:

- `id` — unique identifier string.
- `name` — display name.
- `username` — login username.
- `host` — remote host.
- `port` — remote port.
- `service_type` — service type string.
- `created_at` — ISO-8601 UTC creation timestamp.
- `updated_at` — ISO-8601 UTC last update timestamp.

Sensitive fields stored as `"<iv_hex>:<ciphertext_hex>"` (encrypted):

- `password`
- `private_key`
- `private_key_passphrase`

AES-256-GCM details:

- Fresh 12-byte nonce per encrypted value (`secrets.token_bytes(12)`).
- No additional authenticated data (AAD is `None`).
- Nonce and ciphertext are each hex-encoded and joined with `:`.

Encryption/decryption round-trips through `Account` dataclass:
`add_account` encrypts the three sensitive fields before serialization;
`get_account` detects the `:` separator and decrypts automatically.

## Unlock Flow

1. User enters master password.
2. `detect_version(data)` returns `1` (v1) or `2` (v2).
3. v1 path: validate structure; reject empty salt/key_hash;
    PBKDF2-HMAC-SHA256 with stored `kdf_params` (invalid iterations/length fall back to defaults 100000/32);
   constant-time `hmac.compare_digest` against truncated `key_hash`.
4. v2 path: validate structure; reject empty salt/password_hash;
   Argon2id derive with stored `kdf_params` (int-not-bool, safe-bounds,
   version check); HMAC-SHA256 verifier comparison.
5. On mismatch or Argon2Error: return `False` (fail-closed; no plaintext
   secrets in logs).
6. On success: store derived key in memory; clear on `lock()` or process exit.
7. Unknown version → `False`.

## v1→v2 Upgrade (core API)

`upgrade_vault_v1_to_v2(path: Path, master_password: str) -> VaultUpgradeResult`

Atomic explicit upgrade. Never automatic on startup. Transaction with backup,
verified replacement, and rollback:

1. Load/validate v1 source; hash source bytes.
2. Unlock v1, decrypt all accounts, verify IDs.
3. Create same-directory raw-`0o600` fsynced backup; verify hash.
4. Build v2 candidate (same password, Argon2id defaults, fresh AES-GCM nonces);
   verify all accounts decrypt.
5. Pre-replace hash check; `os.replace` candidate → source.
6. Post-replace verification (hash match).
7. Delete backup (failure returns success with `retained_backup_path`).

**Failure semantics:**

- **Pre-replace failure** (steps 1–5): the source vault is never overwritten;
  the candidate file is cleaned up; any backup that was created is retained.
  No rollback is attempted.
- **Post-replace verification failure** (step 6): a verified rollback from the
  backup is attempted. If rollback fails, `rollback_succeeded` is `False` and
  the backup is retained for manual recovery.

Errors carry `VaultUpgradeError` with secret-safe metadata:
`rollback_succeeded`, `recovery_backup_path`, `source_sha256`, `backup_sha256`.

**No UI or CLI upgrade flow** (Phase 9.9d). Caller must ensure no concurrent
writer.

## UI Rules

- Vault locked: show unlock prompt.
- Vault not configured: show setup prompt.
- Secret reveal requires explicit action.
- Copy-to-clipboard should auto-clear later.

## Tests and Invariants

- `VaultUpgradeResult` is frozen dataclass with all contract fields.
- `VaultUpgradeError` carries only secret-safe recovery metadata.
- Backup is raw byte copy (not plaintext JSON).
- Backup hash must match source hash before and after creation.
- Candidate hash verified against re-decrypted accounts before replace.
- Source hash verified before and after decryption and before replace.
- Post-replace verify all accounts decrypt; hash must match candidate hash.
- Rollback restores original v1 bytes; backup is never modified or deleted.
- Backup deletion failure is a successful upgrade with `retained_backup_path`.
- Installed verification failure triggers rollback; if rollback fails,
  `rollback_succeeded` is `False`, backup retained for manual recovery.
- No orphaned temporary files after success, failure, or rollback.
- 45 upgrade-specific tests cover all paths.

