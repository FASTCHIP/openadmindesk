# SSH Options Mapping

OpenAdminDesk should build OpenSSH commands from structured profile fields.
Never build shell strings.

## Base Command

```text
ssh [options...] user@host
```

If username is empty, use `host` only and let OpenSSH config decide.

## Supported Options

| Profile field | OpenSSH option | Notes |
| --- | --- | --- |
| `port` | `-p <port>` | Validate 1-65535 |
| `identity_file` | `-i <path>` | Path only; never copy key content |
| `proxy_jump` | `-J <jump>` | Prefer over proxy command |
| `proxy_command` | `-o ProxyCommand=<value>` | Advanced field |
| `forward_agent` | `-A` | Off by default |
| `compression` | `-C` | Off by default |
| `server_alive_interval` | `-o ServerAliveInterval=<n>` | Positive integer |
| `server_alive_count_max` | `-o ServerAliveCountMax=<n>` | Positive integer |
| `strict_host_key_checking` | `-o StrictHostKeyChecking=<value>` | Default should omit option |
| `x11.mode=untrusted` | `-X` | Requires local support |
| `x11.mode=trusted` | `-Y` | Requires explicit user choice |
| local tunnel | `-L bind:target` | See tunnel section |
| remote tunnel | `-R bind:target` | See tunnel section |
| dynamic tunnel | `-D bind` | SOCKS proxy |

## Tunnel Argument Formats

Local:

```text
-L <bind_host>:<bind_port>:<target_host>:<target_port>
```

Remote:

```text
-R <bind_host>:<bind_port>:<target_host>:<target_port>
```

Dynamic:

```text
-D <bind_host>:<bind_port>
```

## Terminal Session Options

Interactive terminal sessions should allocate a TTY by default:

```text
-tt
```

Do not add `-tt` to non-interactive file transfer or check commands.

## Remote GUI Launch

Remote GUI launch uses SSH X11 forwarding plus a remote command:

```text
ssh -X user@host <remote-command>
ssh -Y user@host <remote-command>
```

The remote command must be represented as structured arguments when possible.
If the user enters a free-form command, treat it as advanced input and never
mix it with local shell execution.

## Secrets

Passwords and private-key passphrases must not appear in argv. Use OpenSSH
agent, askpass integration, or an interactive prompt flow later.

