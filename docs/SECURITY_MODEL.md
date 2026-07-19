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

Phase 9.9d exposes this API through explicit Qt and standalone CLI flows.
Callers must still ensure exclusive write access during the upgrade.

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

## Tunnel Logging Contract

Tunnel lifecycle events are logged with structured messages containing:
- tunnel_id (UUID string)
- tunnel_type (enum string)
- exit_code (integer, when available)
- exception_class (string, when applicable)

**Allowed fields:** `tunnel_id`, `tunnel_type`, `exit_code`, `exception_class`

**Forbidden fields:** full argv/command, `profile.name`, host, username, `private_key_path`, captured stderr, exception message, traceback, credentials/secrets.

The `last_error()` method remains available to callers for diagnostics but is not exposed in logs.

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

## RDP Certificate Trust (TOFU)

OpenAdminDesk implements Trust On First Use (TOFU) for the built-in RDP client, matching the SSH host-key trust pattern:

- **First Connect**: When connecting to a new RDP server, the FreeRDP certificate verify callback intercepts the server's X.509 certificate. The user is shown a Qt dialog with the hostname, subject, issuer, and SHA-256 fingerprint. No connection proceeds until the user explicitly trusts the certificate.

- **Trusted Certificate Store**: Accepted fingerprints are stored in `~/.config/openadmindesk/rdp_known_certs.json` with file permissions `0600`. Each entry records the hostname, thumbprint, subject, issuer, and timestamp of first trust.

- **Subsequent Connects**: Previously trusted fingerprints are auto-accepted without prompting. If a server presents a different fingerprint, the user is prompted again (potential MITM detection).

- **Auto-accept Policy**: Only profiles with `rdp_certificate_policy = "auto"` skip certificate verification entirely (insecure, not recommended). The `"warn"` policy shows a warning but allows connection. The default TOFU policy prompts for unknown certificates and rejects mismatches.

- **Implementation**: The certificate callback runs on the FreeRDP worker thread and communicates with the UI via Qt signals and a `threading.Event` with a 30-second timeout. The ctypes callback reference is held as an instance variable to prevent garbage-collection crashes.

## RDP Gateway Secrets

RDP profiles must not persist `rdp_gateway_password` in SQLite or exported profile files. Gateway credentials are stored as a dedicated vault account and referenced through `Profile.rdp_gateway_credential_id`, separate from the primary `credential_id`. Runtime profile copies may hydrate `rdp_gateway_password` only after the vault is unlocked.

## Vault Upgrade Security

The vault upgrade process requires explicit user confirmation and a password to be provided. The upgrade is performed in a secure manner with no secrets in command-line arguments, logs, or output.

The `openadmindesk-vault-upgrade` CLI tool:
- Does not accept passwords via command-line arguments
- Uses environment variables or TTY prompts for password input
- Does not display secrets in output
- Requires `--confirm-upgrade` flag to proceed with upgrade
- Provides JSON output for scripting consumers with hash metadata but no secrets
- Vault remains locked after upgrade
- Caller must acknowledge exclusive writer access

The Qt UI upgrade action:
- Shows a warning dialog before proceeding
- Requires explicit confirmation of the upgrade
- Prompts for password via secure input dialog
- Does not display secrets in UI messages
- Locks the vault before upgrade to prevent concurrent access

**Security Notes:**
- No password is passed as command-line argument or logged
- Environment variable sources are supported but not printed; they may be visible to same-user processes via `/proc/<pid>/environ`, so TTY prompts are preferred interactively
- UI uses secure password input fields without hash display
- Explicit writer warning is shown to prevent concurrent access
- Vault remains locked after upgrade to prevent concurrent access

## Telnet Cleartext Warning

When connecting to a Telnet session, a warning dialog is displayed to inform users about the insecure nature of the Telnet protocol. The dialog explicitly states that credentials and session data are transmitted in plaintext over the network, which can be observed by network observers. This warning is shown before every connection attempt, including reconnects.

The warning dialog uses the following parameters:
- Title: "Telnet Connection Warning"
- Body: "This connection uses the Telnet protocol, which transmits credentials and session data in plaintext over the network. Network observers can read your username, password, and all session data. Only use this connection type for trusted legacy systems."
- Buttons: Yes (Proceed) and No (Cancel)
- Default Button: No (Cancel)

The dialog is displayed only in the UI layer, without modifying the TelnetBackend. The default behavior is "No" (cancel connection), and the connection proceeds only when the user selects "Yes". If the dialog cannot be displayed, the connection attempt is cancelled (fail closed).

## Telnet Cleartext Warning Implementation Details

The TelnetSessionTab class implements the warning dialog using the following methods:
1. `_confirm_cleartext_connection()` - Shows the warning dialog and returns a boolean indicating user's choice
2. `_start_connection()` - Starts the connection process after warning confirmation
3. `_connect()` - Connects to Telnet server with warning dialog
4. `_on_reconnect()` - Reconnects to Telnet server with warning dialog

The implementation ensures that:
- Initial connect flow shows warning before connection attempt
- Reconnect flow shows warning before disconnecting and reconnecting
- No double-prompting on reconnect
- UI state is preserved when connection is cancelled
- Backend functionality remains unchanged
- Dialog exception does not call backend

## Tunnel Logging

Tunnel lifecycle events are logged with structured messages containing:
- tunnel_id (UUID string)
- tunnel_type (enum string)
- exit_code (integer, when available)
- exception_class (string, when applicable)

Sensitive information such as host, username, private_key_path, captured stderr, exception messages, and full command lines are never logged. The `last_error()` method remains available to callers for diagnostics but is not exposed in logs.
