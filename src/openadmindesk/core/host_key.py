"""SSH host-key trust helpers."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paramiko
from paramiko.ssh_exception import SSHException


@dataclass(frozen=True)
class HostKeyPrompt:
    """Details shown when a server presents an unknown host key."""

    hostname: str
    key_type: str
    fingerprint_sha256: str
    key: paramiko.PKey


class HostKeyTrustStore:
    """OpenAdminDesk-owned known_hosts file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".config" / "openadmindesk" / "known_hosts"

    def load_into(self, client: paramiko.SSHClient) -> None:
        """Load trusted host keys into a Paramiko client if the file exists."""
        if self.path.exists() and hasattr(client, "load_host_keys"):
            client.load_host_keys(str(self.path))

    def save_host_key(self, hostname: str, key: paramiko.PKey) -> None:
        """Persist a trusted host key."""
        host_keys = paramiko.HostKeys()
        if self.path.exists():
            host_keys.load(str(self.path))
        host_keys.add(hostname, key.get_name(), key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        host_keys.save(str(self.path))

    @staticmethod
    def fingerprint_sha256(key: paramiko.PKey) -> str:
        digest = hashlib.sha256(key.asbytes()).digest()
        encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"SHA256:{encoded}"


HostKeyDecisionCallback = Callable[[HostKeyPrompt], bool]


class TrustOnFirstUsePolicy(paramiko.MissingHostKeyPolicy):
    """Paramiko missing-host-key policy with explicit user approval."""

    def __init__(
        self,
        trust_store: HostKeyTrustStore | None = None,
        decision_callback: HostKeyDecisionCallback | None = None,
    ) -> None:
        self.trust_store = trust_store or HostKeyTrustStore()
        self.decision_callback = decision_callback
        self.pending: HostKeyPrompt | None = None

    def missing_host_key(
        self,
        client: paramiko.SSHClient,
        hostname: str,
        key: paramiko.PKey,
    ) -> None:
        prompt = HostKeyPrompt(
            hostname=hostname,
            key_type=key.get_name(),
            fingerprint_sha256=self.trust_store.fingerprint_sha256(key),
            key=key,
        )
        self.pending = prompt
        if self.decision_callback and self.decision_callback(prompt):
            self.trust_store.save_host_key(hostname, key)
            client.get_host_keys().add(hostname, key.get_name(), key)
            self.pending = None
            return
        raise SSHException(
            "Unknown host key for "
            f"{hostname} ({prompt.key_type} {prompt.fingerprint_sha256}). "
            "Trust this host key before connecting."
        )
