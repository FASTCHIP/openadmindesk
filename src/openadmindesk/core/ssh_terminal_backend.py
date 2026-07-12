"""SSH terminal backend using paramiko (no system ssh required)."""

from __future__ import annotations

import logging
import re
import socket
import threading
from collections.abc import Callable
from typing import Optional

import paramiko
from paramiko.ssh_exception import SSHException

from openadmindesk.core.host_key import HostKeyPrompt, HostKeyTrustStore, TrustOnFirstUsePolicy
from openadmindesk.core.profile import Profile
from openadmindesk.core.terminal_backend import TerminalBackend

logger = logging.getLogger(__name__)


def _is_valid_ssh_input(value: str) -> bool:
    if not value:
        return False
    dangerous_chars = r'[;&|`$(){}<>]'
    if re.search(dangerous_chars, value):
        return False
    if any(ord(char) < 32 for char in value):
        return False
    return True


class SSHTerminalBackend(TerminalBackend):
    """SSH terminal backend using paramiko (pure Python, no system ssh)."""

    def __init__(self, profile: Profile, host_key_store: HostKeyTrustStore | None = None):
        self.profile = profile
        self._host_key_store = host_key_store or HostKeyTrustStore()
        self._pending_host_key: HostKeyPrompt | None = None
        self._client: Optional[paramiko.SSHClient] = None
        self._channel: Optional[paramiko.Channel] = None
        self._connected = False
        self._reader_thread: Optional[threading.Thread] = None
        self._on_output: Optional[Callable[[bytes], None]] = None
        self._last_error: str = ""  # callback(bytes)

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self, on_output: Optional[Callable[[bytes], None]] = None) -> bool:
        """Connect to the SSH server and open an interactive shell.

        Args:
            on_output: Called with raw bytes received from the server.
        """
        self._on_output = on_output
        try:
            host = self.profile.host
            port = self.profile.port
            username = self.profile.username

            if not _is_valid_ssh_input(host):
                logger.error(f"Invalid host: {host}")
                return False
            if username and not _is_valid_ssh_input(username):
                logger.error(f"Invalid username: {username}")
                return False

            self._client = paramiko.SSHClient()
            self._client.load_system_host_keys()
            self._host_key_store.load_into(self._client)
            host_key_policy = TrustOnFirstUsePolicy(self._host_key_store)
            self._client.set_missing_host_key_policy(host_key_policy)

            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username or None,
                "timeout": 15,
                "allow_agent": self.profile.use_ssh_agent,
                "compress": self.profile.compression,
            }

            explicit_key_path = bool(self.profile.private_key_path)
            if self.profile.password:
                connect_kwargs["password"] = self.profile.password

            # Do not let Paramiko silently try ~/.ssh keys for password profiles.
            # Key auth must be explicit through Private Key or SSH agent.
            connect_kwargs["look_for_keys"] = explicit_key_path

            if explicit_key_path:
                connect_kwargs["key_filename"] = self.profile.private_key_path
                if self.profile.private_key_passphrase:
                    connect_kwargs["passphrase"] = self.profile.private_key_passphrase

            # ProxyCommand / Jump host
            if self.profile.proxy_command:
                from paramiko import ProxyCommand
                connect_kwargs["sock"] = ProxyCommand(self.profile.proxy_command)

            self._client.connect(**connect_kwargs)

            # Request a pseudo-terminal
            self._channel = self._client.invoke_shell(
                term="xterm-256color",
                width=120,
                height=40,
            )
            self._channel.settimeout(0.1)

            self._connected = True

            # Start background reader
            self._reader_thread = threading.Thread(
                target=self._read_loop, daemon=True
            )
            self._reader_thread.start()

            self._pending_host_key = None
            logger.info(f"SSH connected to {host}:{port}")
            return True

        except (SSHException, socket.error) as e:
            if 'host_key_policy' in locals():
                self._pending_host_key = host_key_policy.pending
            self._last_error = str(e)
            logger.error(f"SSH connection failed: {e}")
            self._connected = False
            return False
        except Exception as e:
            if 'host_key_policy' in locals():
                self._pending_host_key = host_key_policy.pending
            self._last_error = f"Unexpected: {e}"
            logger.error(f"Unexpected SSH error: {e}")
            self._connected = False
            return False

    def _read_loop(self) -> None:
        """Continuously read from the SSH channel in a background thread."""
        while self._connected and self._channel:
            try:
                if self._channel.recv_ready():
                    data = self._channel.recv(4096)
                    if data and self._on_output:
                        self._on_output(data)
                else:
                    if self._channel.exit_status_ready():
                        break
            except (SSHException, socket.error, OSError):
                break
            except Exception as e:
                logger.debug(f"SSH read loop: {e}")

    def disconnect(self) -> None:
        """Close the SSH connection."""
        self._connected = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("SSH disconnected")

    # ── I/O ───────────────────────────────────────────────────────────────────

    def send(self, data: str) -> None:
        """Send data (keystrokes) to the remote shell."""
        if self._connected and self._channel:
            try:
                self._channel.send(data.encode("utf-8"))
            except (SSHException, socket.error) as e:
                logger.error(f"SSH send error: {e}")

    def write(self, data: str) -> None:
        """Alias for send() — used by TerminalBackend interface."""
        self.send(data)

    def is_connected(self) -> bool:
        return self._connected and self._channel is not None

    def last_error(self) -> str:
        return self._last_error

    def pending_host_key(self) -> HostKeyPrompt | None:
        return self._pending_host_key

    def trust_pending_host_key(self) -> bool:
        if not self._pending_host_key:
            return False
        self._host_key_store.save_host_key(
            self._pending_host_key.hostname,
            self._pending_host_key.key,
        )
        self._pending_host_key = None
        return True

    def get_connection_info(self) -> dict:
        return {
            "host": self.profile.host,
            "port": self.profile.port,
            "username": self.profile.username,
            "connected": self.is_connected(),
        }

    def read(self, size: int = 1024) -> str:
        """Read from SSH channel (non-blocking best-effort)."""
        if self._channel and self._channel.recv_ready():
            try:
                return self._channel.recv(size).decode("utf-8", errors="replace")
            except Exception:
                pass
        return ""

    def get_pid(self) -> Optional[int]:
        """Return None — no subprocess PID with paramiko."""
        return None

    def set_size(self, rows: int, cols: int) -> None:
        """Resize the remote terminal (TTY)."""
        if self._channel:
            try:
                self._channel.resize_pty(width=cols, height=rows)
            except Exception:
                pass

    def get_size(self) -> tuple[int, int]:
        """Return default terminal size."""
        return (24, 80)
