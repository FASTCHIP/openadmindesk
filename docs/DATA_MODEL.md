# Data Model

This document defines the first stable domain objects. Field names should stay
boring and explicit so agents do not invent incompatible variants.

## Profile

```text
name: string
host: string
port: int
username: string | null
credential_id: string | null
private_key_path: string | null
use_ssh_agent: bool
compression: bool
keep_alive: bool
ssh_config: string | null
proxy_command: string | null
created_at: string | null
updated_at: string | null
```

### Validation Rules

- `name` and `host` are required
- `port` must be between 1 and 65535
- `host` must be a valid IPv4 address, IPv6 address, or hostname
- `private_key_path` must be a valid file path if provided
- `ssh_config` must be a valid SSH configuration string if provided

### Host Validation

The following formats are supported for `host`:

- **IPv4**: `192.168.1.1`
- **IPv6**: `2001:db8::1`
- **Hostname**: `example.com` or `sub.example.com`

### Authentication Methods

Profile rows store connection metadata only. Plaintext credentials must not be
written to `profiles` rows or plain JSON/CSV exports.

1. **Vault account**: Set `credential_id` and resolve secrets through the vault.
2. **Private key path**: Set `private_key_path`; the file path is metadata, not
   private key content.
3. **SSH agent**: Set `use_ssh_agent = true`.
4. **Combined**: Can use vault credentials + private key path + SSH agent.

### Security Validation

All input fields are validated to prevent command injection:

- **Hostname**: Must be valid IPv4, IPv6 address, or hostname
- **Username**: Must not contain shell metacharacters
- **Port**: Must be between 1 and 65535
- **Commands**: Sent through SSH are sanitized to prevent injection

### Input Sanitization

The following dangerous characters are removed from inputs:
- Shell metacharacters: `;&|`$(){}<>`
- Control characters (except tab and newline)

### SSH Configuration

The `ssh_config` field can contain additional SSH configuration options
that will be applied to the connection. This should follow standard SSH
config file format.

### Proxy Support

The `proxy_command` field can be used to specify a proxy command for
connecting through a proxy server.

## RDP Gateway Credentials

Profiles may reference two vault accounts: `credential_id` for the primary session login and `rdp_gateway_credential_id` for TS Gateway authentication. The gateway account uses `service_type="rdp-gateway"` and stores the gateway username/password in the encrypted vault. Profile rows keep gateway host/user metadata and always clear `rdp_gateway_password` before persistence/export.
