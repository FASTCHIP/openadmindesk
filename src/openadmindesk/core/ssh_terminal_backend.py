"""SSH terminal backend using paramiko (no system ssh required)."""

from __future__ import annotations

import logging
import queue
import re
import socket
import threading
from collections.abc import Callable
from typing import Optional

import paramiko
from paramiko.ssh_exception import SSHException

from openadmindesk.core.host_key import HostKeyPrompt, HostKeyTrustStore, TrustOnFirstUsePolicy
from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_validation import validate_proxy_command
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
        self._stop_event = threading.Event()
        self._outbound_queue: queue.Queue[bytes] = queue.Queue(maxsize=256)
        self._pending_outbound: bytes = b""
        self._on_output: Optional[Callable[[bytes], None]] = None
        self._last_error: str = ""  # callback(bytes)

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self, on_output: Optional[Callable[[bytes], None]] = None) -> bool:
        """Connect to the SSH server and open an interactive shell.

        Args:
            on_output: Called with raw bytes received from the server.
        """
        self._last_error = ""
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

            # Re-validate proxy command at connect time (profile may have been
            # mutated or imported after construction).
            if self.profile.proxy_command:
                is_valid_proxy, proxy_error = validate_proxy_command(self.profile.proxy_command)
                if not is_valid_proxy:
                    error_msg = f"Proxy command rejected: {proxy_error}"
                    self._last_error = error_msg
                    logger.warning("Proxy command rejected: %s", proxy_error)
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
            self._stop_event.clear()
            self._outbound_queue = queue.Queue(maxsize=256)
            self._pending_outbound = b""
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
        while self._connected and self._channel and not self._stop_event.is_set():
            try:
                made_progress = False
                if self._flush_outbound():
                    made_progress = True
                if self._channel.recv_ready():
                    data = self._channel.recv(4096)
                    if data and self._on_output and not self._stop_event.is_set():
                        self._on_output(data)
                    made_progress = True
                if not made_progress:
                    if self._channel.exit_status_ready():
                        break
                    self._stop_event.wait(timeout=0.1)
            except (SSHException, socket.error, OSError):
                break
            except Exception as e:
                logger.debug(f"SSH read loop: {e}")

    def _flush_outbound(self) -> bool:
        """Attempt one send of pending outbound data (reader thread only).

        Returns True if any progress was made (data sent), False otherwise.
        """
        channel = self._channel
        if not channel:
            return False
        pending = self._pending_outbound
        if not pending:
            try:
                pending = self._outbound_queue.get_nowait()
            except queue.Empty:
                return False
        if not channel.send_ready():
            self._pending_outbound = pending
            return False
        try:
            n = channel.send(pending)
        except (SSHException, socket.error, OSError):
            self._pending_outbound = pending
            return False
        if n > 0:
            self._pending_outbound = pending[n:]
            return True
        self._pending_outbound = pending
        return False

    def _clear_outbound(self) -> None:
        """Empty queued chunks and reset pending outbound data."""
        while not self._outbound_queue.empty():
            try:
                self._outbound_queue.get_nowait()
            except queue.Empty:
                break
        self._pending_outbound = b""

    def disconnect(self) -> None:
        """Close the SSH connection."""
        self._connected = False
        self._stop_event.set()
        reader = self._reader_thread
        self._reader_thread = None
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
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=0.5)
        self._clear_outbound()
        logger.info("SSH disconnected")

    # ── I/O ───────────────────────────────────────────────────────────────────

    def send(self, data: str) -> None:
        """Enqueue data (keystrokes) for the remote shell (nonblocking)."""
        if not (self._connected and self._channel):
            return
        try:
            self._outbound_queue.put_nowait(data.encode("utf-8"))
        except queue.Full:
            logger.warning("SSH outbound queue full; dropping input chunk")

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
