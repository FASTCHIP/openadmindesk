"""Profile data model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re
from openadmindesk.core.profile_validation import is_safe_ssh_token, validate_proxy_command


class SessionType(Enum):
    """Type of remote session."""
    SSH = "ssh"
    RDP = "rdp"
    TELNET = "telnet"
    LOCAL_SHELL = "local"
    VNC = "vnc"


@dataclass
class Profile:
    """Profile data model."""
    
    # Basic connection info
    name: str = ""
    host: str = ""
    port: int = 22
    username: str = ""
    session_type: SessionType = SessionType.SSH
    
    # Authentication
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    
    # Connection options
    use_ssh_agent: bool = False
    compression: bool = False
    keep_alive: bool = True
    x11_forwarding: bool = False
    
    # Advanced options
    ssh_config: Optional[str] = None
    proxy_command: Optional[str] = None
    
    # RDP options
    rdp_drive_redirection: bool = False
    rdp_drive_path: Optional[str] = None       # local path to share
    rdp_printer_redirection: bool = False
    rdp_clipboard_redirection: bool = True
    rdp_multimon: bool = False                  # use all monitors
    rdp_certificate_policy: str = "auto"        # auto, warn, ignore
    rdp_gateway: Optional[str] = None           # TS Gateway host
    rdp_gateway_username: Optional[str] = None
    rdp_gateway_password: Optional[str] = None
    rdp_gateway_credential_id: Optional[str] = None
    rdp_nla: bool = True                    # Network Level Authentication
    rdp_domain: str = ""                    # Windows domain for NLA
    
    # VNC options
    vnc_scaling: bool = False
    vnc_view_only: bool = False
    vnc_color_depth: int = 24                   # 8, 16, 24, 32
    vnc_encoding: str = "tight"                   # tight, zrle, hextile, raw
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parent_folder: Optional[str] = None
    credential_id: Optional[str] = None
    terminal_theme: str = "Dark"
    notes: str = ""
    favorite: bool = False
    tags: str = ""                 # comma-separated tags
    icon_id: Optional[str] = None
    last_connected: Optional[str] = None  # ISO-8601 timestamp
    last_error: Optional[str] = None
    last_duration: Optional[float] = None  # seconds
    
    @property
    def tag_list(self) -> list[str]:
        """Return tags as a parsed list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]
    
    def __post_init__(self) -> None:
        """Initialize the profile."""
        # Don't auto-fill name — validation will catch empty names
    
    def is_valid(self) -> bool:
        """Validate the profile."""
        if not self.name:
            return False
        if self.session_type == SessionType.LOCAL_SHELL:
            return True
        if not self.host:
            return False

        # Validate host format
        if not self._is_valid_host(self.host):
            return False

        if self.username and not is_safe_ssh_token(self.username):
            return False

        # Validate port
        if not (1 <= self.port <= 65535):
            return False

        if self.proxy_command:
            is_valid_proxy, _error = validate_proxy_command(self.proxy_command)
            if not is_valid_proxy:
                return False

        return True

    @property
    def icon(self) -> str:
        """Return a compact text fallback for session type."""
        if self.session_type == SessionType.RDP:
            return "RDP"
        if self.session_type == SessionType.TELNET:
            return "TN"
        if self.session_type == SessionType.LOCAL_SHELL:
            return "SH"
        if self.session_type == SessionType.VNC:
            return "VNC"
        return "SSH"
    
    @property
    def description(self) -> str:
        """Return human-readable description (user@host:port)."""
        return f"{self.username}@{self.host}:{self.port}" if self.username else f"{self.host}:{self.port}"
    
    def _is_valid_host(self, host: str) -> bool:
        """Validate host address format."""
        if not is_safe_ssh_token(host):
            return False

        # IPv4 address
        if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host):
            # Validate each octet
            octets = host.split('.')
            for octet in octets:
                if int(octet) > 255:
                    return False
            return True
            
        # IPv6 address
        if re.match(r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$', host):
            return True
            
        # Hostname
        if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', host):
            return True
            
        return False
