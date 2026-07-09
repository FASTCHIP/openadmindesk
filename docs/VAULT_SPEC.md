# Vault Specification

The credential vault stores secrets for accounts. It is separate from
connection profile metadata.

## Goals

- Encrypt secrets at rest.
- Never store the master password.
- Keep account metadata searchable without exposing secrets.
- Make testing possible with fake secrets only.

## Storage

Initial implementation may use:

```text
~/.local/share/openadmindesk/vault.json
```

or an encrypted SQLite table. The chosen format must be recorded in
`docs/DECISIONS.md` before implementation.

## Key Derivation

Use Argon2id with:

- random 16-byte or larger salt,
- memory cost chosen for desktop use,
- parameters stored next to vault metadata,
- per-vault salt, not per-secret salt.

The exact parameters must be documented in code and tests.

## Encryption

Use AES-256-GCM:

- random nonce per encrypted value,
- authenticated additional data may include secret ID and vault version,
- never reuse a nonce with the same key,
- store ciphertext, nonce, algorithm, and version.

## Vault Metadata

```text
version: int
kdf: "argon2id"
kdf_params: object
salt: base64
created_at: datetime
updated_at: datetime
```

## Secret Record

```text
id: string
kind: "password" | "key_passphrase" | "note"
nonce: base64
ciphertext: base64
created_at: datetime
updated_at: datetime
```

## Unlock Flow

1. User enters master password.
2. Derive key with stored KDF parameters.
3. Verify by decrypting a small vault check record.
4. Keep derived key in memory only while unlocked.
5. Clear key on lock or application exit.

## UI Rules

- Vault locked: show unlock prompt.
- Vault not configured: show setup prompt.
- Secret reveal requires explicit action.
- Copy-to-clipboard should auto-clear later.

## Tests

- Encrypt/decrypt round trip with fake secret.
- Wrong master password fails.
- Two encryptions of same plaintext produce different ciphertext.
- Vault metadata does not contain plaintext secret.

