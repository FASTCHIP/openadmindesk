# Security Model

## Goals

- Keep secrets encrypted at rest.
- Avoid leaking secrets through logs, crash reports, command lines, or shell
  history.
- Preserve normal OpenSSH security behavior.
- Make destructive actions explicit.

## Credential Vault

The vault should use:

- master password,
- random salt,
- Argon2id key derivation,
- AES-256-GCM encryption,
- random nonce per encrypted value.

The master password must never be stored.

## Accounts

Account records may contain:

- display name,
- username,
- password,
- private-key passphrase,
- notes,
- tags.

Host profiles reference accounts by internal ID.

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

