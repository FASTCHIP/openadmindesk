"""Tunnel profile model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from openadmindesk.core.profile_validation import _is_valid_host, is_safe_ssh_token
from enum import Enum


class TunnelType(Enum):
    """Enumeration of tunnel types."""
    LOCAL_FORWARD = "local_forward"
    REMOTE_FORWARD = "remote_forward"
    DYNAMIC_SOCKS = "dynamic_socks"


@dataclass
class TunnelProfile:
    """Tunnel profile model."""
    
    # Unique identifier
    id: Optional[str] = None
    
    # Tunnel name
    name: str = ""
    
    # Connection information
    host: str = ""
    port: int = 22
    username: str = ""
    
    # Tunnel type
    tunnel_type: TunnelType = TunnelType.LOCAL_FORWARD
    
    # Local port (for local forwards)
    local_port: int = 0
    
    # Remote port (for remote forwards)
    remote_port: int = 0
    
    # Remote host (for remote forwards)
    remote_host: str = "localhost"
    
    # SOCKS port (for dynamic SOCKS)
    socks_port: int = 0
    
    # SSH options
    private_key_path: Optional[str] = None
    compression: bool = False
    keep_alive: bool = True
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Initialize the tunnel profile."""
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())
    
    def is_valid(self) -> bool:
        """Validate the tunnel profile."""
        if not self.name or not self.host:
            return False
        if not _is_valid_host(self.host):
            return False
        if self.username and not is_safe_ssh_token(self.username):
            return False
        if not (1 <= self.port <= 65535):
            return False

        # Validate port numbers (must be 1-65535 when set)
        if self.tunnel_type == TunnelType.LOCAL_FORWARD:
            if not self.local_port or not (1 <= self.local_port <= 65535):
                return False
            if not self.remote_host or not _is_valid_host(self.remote_host):
                return False
            if not self.remote_port or not (1 <= self.remote_port <= 65535):
                return False
        elif self.tunnel_type == TunnelType.REMOTE_FORWARD:
            if not self.remote_port or not (1 <= self.remote_port <= 65535):
                return False
            if not self.local_port or not (1 <= self.local_port <= 65535):
                return False
            if not self.remote_host or not _is_valid_host(self.remote_host):
                return False
        elif self.tunnel_type == TunnelType.DYNAMIC_SOCKS:
            if not self.socks_port or not (1 <= self.socks_port <= 65535):
                return False

        return True

    def get_ssh_options(self) -> list[str]:
        """Get SSH options for this tunnel."""
        options = []
        
        # Add basic SSH options
        if self.port != 22:
            options.extend(['-p', str(self.port)])
        
        if self.username:
            options.extend(['-l', self.username])
        
        if self.private_key_path:
            options.extend(['-i', self.private_key_path])
        
        if self.compression:
            options.append('-C')
        
        # Add tunnel-specific options
        if self.tunnel_type == TunnelType.LOCAL_FORWARD:
            if self.local_port and self.remote_host and self.remote_port:
                options.extend(['-L', f"{self.local_port}:{self.remote_host}:{self.remote_port}"])
        elif self.tunnel_type == TunnelType.REMOTE_FORWARD:
            if self.remote_port and self.local_port:
                options.extend(['-R', f"{self.remote_port}:{self.remote_host}:{self.local_port}"])
        elif self.tunnel_type == TunnelType.DYNAMIC_SOCKS:
            if self.socks_port:
                options.extend(['-D', str(self.socks_port)])
        
        return options