"""Local shell backend — runs bash/cmd with PTY on Linux, pipes on Windows."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Optional

from openadmindesk.platform.platform_utils import is_windows

logger = logging.getLogger(__name__)


class LocalShellBackend:
    """Backend for a local terminal (bash/cmd) using PTY."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._fd: Optional[int] = None
        self._connected = False
        self._thread: Optional[threading.Thread] = None

    def connect(self, on_output: Optional[callable] = None) -> bool:
        """Start a local shell session.

        Args:
            on_output: Called with str data from the shell.
        """
        try:
            if is_windows():
                return self._connect_windows(on_output)
            else:
                return self._connect_linux(on_output)
        except Exception as e:
            logger.error(f"Local shell failed: {e}")
            return False

    def _connect_linux(self, on_output: Optional[callable] = None) -> bool:
        """Use pty to create a pseudo-terminal."""
        import pty as pty_module  # avoids shadowing

        master_fd, slave_fd = pty_module.openpty()
        self._fd = master_fd

        self._process = subprocess.Popen(
            ["bash", "--login"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave_fd)

        self._connected = True

        if on_output:
            self._thread = threading.Thread(
                target=self._read_loop_pty, args=(on_output,), daemon=True
            )
            self._thread.start()

        logger.info("Local shell started (PTY)")
        return True

    def _connect_windows(self, on_output: Optional[callable] = None) -> bool:
        """Use pipes on Windows."""
        self._process = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
        )
        self._connected = True

        if on_output:
            self._thread = threading.Thread(
                target=self._read_loop_pipe, args=(on_output,), daemon=True
            )
            self._thread.start()

        logger.info("Local shell started (Windows)")
        return True

    def _read_loop_pty(self, on_output: callable) -> None:
        """Read from PTY in background thread."""
        import select

        while self._connected and self._fd is not None:
            try:
                r, _, _ = select.select([self._fd], [], [], 0.1)
                if r:
                    data = os.read(self._fd, 4096).decode("utf-8", errors="replace")
                    if data:
                        on_output(data)
            except (OSError, ValueError):
                break

    def _read_loop_pipe(self, on_output: callable) -> None:
        """Read from pipe in background thread."""
        while self._connected and self._process and self._process.stdout:
            try:
                data = self._process.stdout.readline()
                if not data:
                    break
                on_output(data.decode("utf-8", errors="replace"))
            except Exception:
                break

    def send(self, data: str) -> None:
        """Send data to the shell."""
        if self._process:
            try:
                if self._fd is not None:
                    os.write(self._fd, data.encode("utf-8"))
                elif self._process.stdin:
                    self._process.stdin.write(data.encode("utf-8"))
                    self._process.stdin.flush()
            except (OSError, ValueError) as e:
                logger.error(f"Local shell send error: {e}")

    def disconnect(self) -> None:
        """Terminate the local shell."""
        self._connected = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None

    def is_connected(self) -> bool:
        if self._process:
            return self._process.poll() is None
        return False
