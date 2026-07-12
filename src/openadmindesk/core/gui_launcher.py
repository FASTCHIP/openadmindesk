"""GUI launcher with X11 forwarding."""

from __future__ import annotations

import logging
import subprocess

from openadmindesk.core.tunnel_profile import TunnelProfile
from openadmindesk.core.x11_detector import X11Detector
from openadmindesk.core.ssh_terminal_backend import _is_valid_ssh_input


logger = logging.getLogger(__name__)


class GuiLauncher:
    """Launches GUI applications with X11 forwarding."""
    
    def __init__(self) -> None:
        """Initialize the GUI launcher."""
        self.x11_detector = X11Detector()
    
    def launch_gui_app(self, profile: TunnelProfile, command: str, 
                   x11_forwarding: bool = True) -> bool:
        """Launch a GUI application with optional X11 forwarding."""
        try:
            # Validate inputs to prevent command injection
            if not _is_valid_ssh_input(profile.host):
                logger.error(f"Invalid host in tunnel profile: {profile.host}")
                return False
            
            if profile.username and not _is_valid_ssh_input(profile.username):
                logger.error(f"Invalid username in tunnel profile: {profile.username}")
                return False

            # Build SSH command
            cmd = ["ssh"]
            
            # Add SSH options from profile
            cmd.extend(profile.get_ssh_options())
            
            # Add X11 forwarding if requested
            if x11_forwarding and self.x11_detector.is_x11_available():
                cmd.extend(["-X", "-Y"])
            
            # Add target
            if profile.username:
                target = f"{profile.username}@{profile.host}"
            else:
                target = profile.host
            
            cmd.append(target)
            
            # Use shell=False and split command into arguments to prevent injection
            # This ensures the command is executed as a single argument to ssh
            cmd.extend(["--", command])
            
            # Start the process with shell=False for security
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False  # Prevent shell injection
            )
            
            return True
        except Exception as e:
            # Log the error but don't expose sensitive information
            logger.error(f"Failed to launch GUI application: {e}")
            return False
    
    def is_x11_forwarding_available(self) -> bool:
        """Check if X11 forwarding is available."""
        return self.x11_detector.is_x11_available()