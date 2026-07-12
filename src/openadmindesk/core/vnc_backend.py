"""VNC backend — uses system VNC viewer or Python vncdotool."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from typing import Optional

from openadmindesk.core.profile import Profile
from openadmindesk.platform.platform_utils import safe_popen_kwargs, is_windows

logger = logging.getLogger(__name__)


def _find_vnc_viewer() -> Optional[str]:
    """Find a VNC viewer on the system."""
    viewers = ["vncviewer", "vinagre", "remmina", "krdc"]
    for v in viewers:
        path = shutil.which(v)
        if path:
            return v
    if is_windows():
        # Check common VNC viewer locations
        import os
        for prog in ["vncviewer.exe", "UltraVNC.exe", "TightVNC.exe", "RealVNC.exe"]:
            for root in [os.environ.get("ProgramFiles", ""),
                         os.environ.get("ProgramFiles(x86)", "")]:
                for dirpath, _, filenames in os.walk(root):
                    if prog in filenames:
                        return os.path.join(dirpath, prog)
    return None


class VncBackend:
    """Launches a VNC viewer as an external process."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.process: Optional[subprocess.Popen] = None
        self._connected = False
        self._stderr_lines: list[str] = []
        self._stderr_thread: Optional[threading.Thread] = None
        self._viewer = _find_vnc_viewer()

    def connect(self) -> bool:
        if not self._viewer:
            logger.error("No VNC viewer found")
            return False

        try:
            host = self.profile.host
            port = self.profile.port or 5900

            if "vncviewer" in self._viewer:
                cmd = [self._viewer, f"{host}:{port}"]
            else:
                cmd = [self._viewer, f"{host}:{port}"]

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
            logger.error(f"VNC launch failed: {e}")
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

    def disconnect(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self._connected = False

    def is_connected(self) -> bool:
        if self.process:
            return self.process.poll() is None
        return False

    @staticmethod
    def is_available() -> bool:
        return _find_vnc_viewer() is not None
