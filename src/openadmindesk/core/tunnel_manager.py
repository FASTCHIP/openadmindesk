"""Tunnel manager."""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Optional, Dict

from openadmindesk.core.tunnel_profile import TunnelProfile
from openadmindesk.platform.platform_utils import safe_popen_kwargs

logger = logging.getLogger(__name__)


class TunnelManager:
    """Manages SSH tunnels."""

    def __init__(self) -> None:
        """Initialize the tunnel manager."""
        self._tunnels: Dict[str, TunnelProcess] = {}

    def start_tunnel(self, profile: TunnelProfile) -> bool:
        """Start a tunnel."""
        try:
            # Create tunnel process
            tunnel_process = TunnelProcess(profile)

            # Start the process
            success = tunnel_process.start()
            if success:
                self._tunnels[profile.id] = tunnel_process
                return True
            else:
                return False
        except Exception:
            return False

    def stop_tunnel(self, tunnel_id: str) -> bool:
        """Stop a tunnel."""
        if tunnel_id in self._tunnels:
            tunnel_process = self._tunnels[tunnel_id]
            success = tunnel_process.stop()
            if success:
                del self._tunnels[tunnel_id]
                return True
        return False

    def is_tunnel_running(self, tunnel_id: str) -> bool:
        """Check if a tunnel is running."""
        if tunnel_id in self._tunnels:
            return self._tunnels[tunnel_id].is_running()
        return False

    def get_tunnel_status(self, tunnel_id: str) -> Optional[Dict[str, any]]:
        """Get tunnel status."""
        if tunnel_id in self._tunnels:
            return self._tunnels[tunnel_id].get_status()
        return None


class TunnelProcess:
    """Represents a running tunnel process."""

    def __init__(self, profile: TunnelProfile) -> None:
        """Initialize the tunnel process."""
        self.profile = profile
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_lines: list[str] = []

    def start(self) -> bool:
        """Start the tunnel."""
        try:
            # Log tunnel start request before attempting Popen
            logger.info("Tunnel start requested", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
            })

            # Build SSH command
            cmd = ["ssh"]

            # Add SSH options from profile
            cmd.extend(self.profile.get_ssh_options())

            # Add target
            if self.profile.username:
                target = f"{self.profile.username}@{self.profile.host}"
            else:
                target = self.profile.host

            cmd.append(target)

            # Add command to keep tunnel open
            cmd.extend(["-o", "ServerAliveInterval=60", "-o", "ServerAliveCountMax=3"])

            # Start the process (platform-safe)
            popen_kwargs = safe_popen_kwargs()
            popen_kwargs.update({
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
            })
            self._process = subprocess.Popen(cmd, **popen_kwargs)
            self._start_stderr_capture()

            self._running = True

            # Start monitoring thread
            self._thread = threading.Thread(target=self._monitor_process, daemon=True)
            self._thread.start()

            logger.info("Tunnel started successfully", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
            })

            return True
        except Exception as e:
            self._running = False
            logger.warning("Tunnel start failed", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
                "exception_class": e.__class__.__name__,
            })
            return False

    def stop(self) -> bool:
        """Stop the tunnel."""
        try:
            # Log tunnel stop request before attempting stop/terminate
            logger.info("Tunnel stop requested", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
            })

            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()

            self._running = False

            # Log completion with exit code if available
            exit_code = self._process.returncode if self._process else None
            logger.info("Tunnel stopped", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
                "exit_code": exit_code,
            })

            return True
        except Exception as e:
            logger.warning("Tunnel stop failed", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
                "exception_class": e.__class__.__name__,
            })
            return False

    def is_running(self) -> bool:
        """Check if tunnel is running."""
        return self._running and self._process and self._process.poll() is None

    def get_status(self) -> Dict[str, any]:
        """Get tunnel status."""
        return {
            "id": self.profile.id,
            "name": self.profile.name,
            "running": self.is_running(),
            "tunnel_type": self.profile.tunnel_type.value,
            "last_error": self.last_error(),
        }

    def last_error(self) -> str:
        """Return captured process stderr, if any."""
        return "\n".join(self._stderr_lines)

    def _start_stderr_capture(self) -> None:
        """Capture process stderr in the background for diagnostics."""
        if not self._process or not self._process.stderr:
            return
        self._stderr_lines.clear()
        self._stderr_thread = threading.Thread(
            target=self._capture_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stderr_thread.start()

    def _capture_stderr(self, stream) -> None:
        for line in stream:
            text = line.strip()
            if text:
                self._stderr_lines.append(text)
                self._stderr_lines = self._stderr_lines[-20:]

    def _monitor_process(self) -> None:
        """Monitor the process."""
        if self._process:
            # Wait for process to finish
            self._process.wait()
            self._running = False

            # Log completion with exit code
            logger.info("Tunnel process completed", extra={
                "tunnel_id": self.profile.id,
                "tunnel_type": self.profile.tunnel_type.value,
                "exit_code": self._process.returncode,
            })
