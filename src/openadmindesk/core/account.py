"""Account model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import secrets
import string


@dataclass
class Account:
    """Account model for credential management."""
    
    # Unique identifier
    id: Optional[str] = None
    
    # Account information
    name: str = ""
    username: str = ""
    password: Optional[str] = None
    private_key: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    
    # Connection information
    host: str = ""
    port: int = 22
    service_type: str = "ssh"  # ssh, sftp, rdp, rdp-gateway, etc.
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Initialize the account."""
        if not self.id:
            # Generate a unique ID for the account
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate a unique ID for the account."""
        # Create a simple ID using timestamp and random string
        import time
        timestamp = str(int(time.time()))
        random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        return f"{timestamp}_{random_part}"
    
    def is_valid(self) -> bool:
        """Validate the account."""
        if not self.name or not self.username:
            return False
        
        if not self.host:
            return False
            
        return True