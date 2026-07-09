# Data Model

This document defines the first stable domain objects. Field names should stay
boring and explicit so agents do not invent incompatible variants.

## ConnectionProfile

```text
id: string
name: string
folder_id: string | null
protocol: "ssh"
host: string
port: int
username: string | null
account_id: string | null
identity_file: string | null
working_directory: string | null
notes: string
tags: list[string]
ssh_options: SshOptions
tunnels: list[TunnelProfile]
x11: X11Profile
created_at: datetime
updated_at: datetime
```

## Folder

```text
id: string
parent_id: string | null
name: string
sort_order: int
created_at: datetime
updated_at: datetime
```

## Account

```text
id: string
display_name: string
username: string | null
secret_refs: AccountSecretRefs
notes: string
tags: list[string]
created_at: datetime
updated_at: datetime
```

Secrets are referenced by ID and stored in the vault, not plaintext database
columns.

## AccountSecretRefs

```text
password_ref: string | null
key_passphrase_ref: string | null
```

## SshOptions

```text
proxy_jump: string | null
proxy_command: string | null
forward_agent: bool
compression: bool
server_alive_interval: int | null
server_alive_count_max: int | null
strict_host_key_checking: "default" | "yes" | "accept-new" | "no"
```

Use `"no"` only when the user explicitly chooses insecure behavior.

## TunnelProfile

```text
id: string
name: string
kind: "local" | "remote" | "dynamic"
bind_host: string
bind_port: int
target_host: string | null
target_port: int | null
enabled: bool
```

Dynamic SOCKS tunnels do not use `target_host` or `target_port`.

## X11Profile

```text
mode: "disabled" | "untrusted" | "trusted"
remote_command: string | null
```

`untrusted` maps to `ssh -X`. `trusted` maps to `ssh -Y`.

## Snippet

```text
id: string
name: string
body: string
tags: list[string]
created_at: datetime
updated_at: datetime
```

## RecentSession

```text
id: string
profile_id: string
opened_at: datetime
last_status: "connected" | "closed" | "failed"
```

