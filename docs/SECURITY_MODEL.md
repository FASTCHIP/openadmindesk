# Security Model

## Goals

- Keep secrets encrypted at rest.
- Avoid leaking secrets through logs, crash reports, command lines, or shell
  history.
- Preserve normal OpenSSH security behavior.
- Make destructive actions explicit.

## Credential Vault

The current vault implementation uses:

- master password,
- random salt,
- PBKDF2-HMAC-SHA256 key derivation with 100k iterations,
- AES-256-GCM encryption,
- random nonce per encrypted value.

Argon2id is still a planned hardening task, not current behavior.

The master password must never be stored.

## Accounts

Account records may contain:

- display name,
- username,
- password,
- private-key passphrase,
- notes,
- tags.

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
