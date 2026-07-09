# Feature Matrix

Use this table to track product coverage. Agents should update it when a
feature moves from planned to implemented or tested.

| Feature | MVP | Implemented | Tested | Notes |
| --- | --- | --- | --- | --- |
| Main window shell | yes | no | no | Toolbar, tree, tabs, status area |
| Connection tree | yes | no | no | Folders, profiles, search |
| SSH profile model | yes | no | no | See `docs/DATA_MODEL.md` |
| OpenSSH argv builder | yes | no | no | See `docs/SSH_OPTIONS.md` |
| Tabbed terminal workspace | yes | no | no | Backend abstraction first |
| SFTP browser | yes | no | no | List, upload, download |
| Credential vault | yes | no | no | See `docs/VAULT_SPEC.md` |
| Account manager UI | yes | no | no | Links accounts to profiles |
| Local forwards | yes | no | no | SSH `-L` |
| Remote forwards | yes | no | no | SSH `-R` |
| Dynamic SOCKS forwards | yes | no | no | SSH `-D` |
| X11 forwarding | yes | no | no | SSH `-X`/`-Y`, local support check |
| Remote GUI launcher | yes | no | no | Runs a remote command with X11 |
| Snippets | later | no | no | Command insertion |
| Import/export | yes | no | no | Profiles first, vault later |
| AppImage packaging | yes | no | no | First release artifact |
| Debian package | later | no | no | After AppImage |
| RPM package | later | no | no | After AppImage |

