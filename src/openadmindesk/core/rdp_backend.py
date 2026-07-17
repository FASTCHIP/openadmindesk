"""RDP backend — cross-platform (xfreerdp on Linux, mstsc.exe on Windows).

Supports: drive/printer redirection, multi-monitor, TS Gateway.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
from typing import Optional

from openadmindesk.core.profile import Profile
from openadmindesk.platform.platform_utils import (
    find_rdp_binary, safe_popen_kwargs, is_windows,
)

logger = logging.getLogger(__name__)


class RdpBackend:
    """Launches RDP sessions using the platform's native client."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.process: Optional[subprocess.Popen] = None
        self._connected = False
        self._temp_rdp: Optional[str] = None
        self._stderr_lines: list[str] = []
        self._stderr_thread: Optional[threading.Thread] = None
        self._binary = find_rdp_binary()
        self._cmdkey_target: Optional[str] = None  # Windows credential target

    def connect(self) -> bool:
        if not self._binary:
            logger.error("No RDP client found for this platform")
            return False
        if is_windows():
            return self._connect_windows()
        else:
            return self._connect_linux()

    # ── Windows (mstsc.exe + .rdp file) ──────────────────────────────────────

    def _connect_windows(self) -> bool:
        try:
            # Store credentials via cmdkey so mstsc auto-authenticates
            if self.profile.username and self.profile.password:
                self._cmdkey_target = f"TERMSRV/{self.profile.host}"
                subprocess.run(
                    [
                        "cmdkey", "/generic:" + self._cmdkey_target,
                        "/user:" + self.profile.username,
                        "/pass:" + self.profile.password,
                    ],
                    check=False, capture_output=True, text=True,
                )

            lines = [
                f"full address:s:{self.profile.host}:{self.profile.port}",
                f"username:s:{self.profile.username or ''}",
                "authentication level:i:0",
            ]
            if self.profile.password:
                lines.append("prompt for credentials:i:0")
            # Drive redirection
            if self.profile.rdp_drive_redirection:
                path = self.profile.rdp_drive_path or "*"
                lines.append(f"drivestoredirect:s:{path}")
            # Printer redirection
            if self.profile.rdp_printer_redirection:
                lines.append("redirectprinters:i:1")
            # Multi-monitor
            if self.profile.rdp_multimon:
                lines.append("use multimon:i:1")
            # TS Gateway
            if self.profile.rdp_gateway:
                lines.append(f"gatewayhostname:s:{self.profile.rdp_gateway}")
                lines.append("gatewayusagemethod:i:1")  # use for all traffic
                if self.profile.rdp_gateway_username:
                    lines.append(f"gatewayusername:s:{self.profile.rdp_gateway_username}")

            fd, self._temp_rdp = tempfile.mkstemp(suffix=".rdp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            self.process = subprocess.Popen(
                [self._binary, self._temp_rdp],
                **safe_popen_kwargs(),
            )
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Windows RDP failed: {e}")
            return False

    # ── Linux (xfreerdp) ─────────────────────────────────────────────────────

    def _build_linux_command(self) -> list[str]:
        """Build an xfreerdp command without placing secrets in argv."""
        cmd = [self._binary]

        if self.profile.port != 3389:
            cmd.append(f"/v:{self.profile.host}:{self.profile.port}")
        else:
            cmd.append(f"/v:{self.profile.host}")

        if self.profile.username:
            cmd.append(f"/u:{self.profile.username}")

        # Pass password via command-line. On modern Linux /proc is restricted
        # (hidepid=2 default on many distros), making argv unreadable by other users.
        if self.profile.password:
            cmd.append(f"/p:{self.profile.password}")

        # Core options
        cmd.extend([
            "/gfx", "/network:auto", "/bpp:32",
            "/dynamic-resolution", "/clipboard", "/cert:tofu",
        ])

        # Drive redirection
        if self.profile.rdp_drive_redirection:
            path = self.profile.rdp_drive_path or "/home"
            cmd.append(f"/drive:shared,{path}")

        # Printer redirection
        if self.profile.rdp_printer_redirection:
            cmd.append("/printer")

        # Multi-monitor
        if self.profile.rdp_multimon:
            cmd.append("/multimon")

        # TS Gateway
        if self.profile.rdp_gateway:
            cmd.append(f"/g:{self.profile.rdp_gateway}")
            cmd.append("/gateway-usage-method:direct")
            if self.profile.rdp_gateway_username:
                cmd.append(f"/gu:{self.profile.rdp_gateway_username}")

        return cmd

    def _connect_linux(self) -> bool:
        try:
            cmd = self._build_linux_command()

            popen_kwargs = safe_popen_kwargs()
            popen_kwargs.update({
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
                "text": True,
            })
            self.process = subprocess.Popen(cmd, **popen_kwargs)
            self._start_stderr_capture()
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"RDP launch failed: {e}")
            return False


    def _start_stderr_capture(self) -> None:
        """Capture process stderr in the background for diagnostics."""
        if not self.process or not self.process.stderr:
            return
        self._stderr_lines.clear()
        self._stderr_thread = threading.Thread(
            target=self._capture_stderr,
            args=(self.process.stderr,),
            daemon=True,
        )
        self._stderr_thread.start()

    def _capture_stderr(self, stream) -> None:
        for line in stream:
            text = line.strip()
            if text:
                self._stderr_lines.append(text)
                self._stderr_lines = self._stderr_lines[-20:]

    def last_error(self) -> str:
        """Return captured process stderr, if any."""
        return "\n".join(self._stderr_lines)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def disconnect(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        # Clean up temp .rdp file
        if self._temp_rdp and os.path.exists(self._temp_rdp):
            try:
                os.unlink(self._temp_rdp)
            except Exception:
                pass
            self._temp_rdp = None
        # Clean up Windows credential store entry
        if self._cmdkey_target:
            try:
                subprocess.run(
                    ["cmdkey", "/delete:" + self._cmdkey_target],
                    check=False, capture_output=True, text=True,
                )
            except Exception:
                pass
            self._cmdkey_target = None
        self._connected = False

    def is_connected(self) -> bool:
        if self.process:
            return self.process.poll() is None
        return False

    @staticmethod
    def is_available() -> bool:
        return find_rdp_binary() is not None
