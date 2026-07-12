"""Remote file model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class FileType(Enum):
    """Enumeration of file types."""
    FILE = "file"
    DIRECTORY = "directory"
    LINK = "link"
    OTHER = "other"


@dataclass
class RemoteFile:
    """Model for remote files and directories."""
    
    # File path
    path: str
    
    # File metadata
    name: str = ""
    size: int = 0
    file_type: FileType = FileType.FILE
    
    # Permissions
    permissions: str = ""
    owner: str = ""
    group: str = ""
    
    # Timestamps
    modified_at: Optional[str] = None
    created_at: Optional[str] = None
    
    # Additional metadata
    is_hidden: bool = False
    is_executable: bool = False
    
    def __post_init__(self) -> None:
        """Initialize the remote file."""
        # Normalize path: strip trailing slash for name extraction
        clean_path = self.path.rstrip('/')
        # Extract name from path if not provided
        if not self.name:
            self.name = clean_path.split('/')[-1] if clean_path else ""
        
        # Keep the file type supplied by protocol backends. Paths alone are not
        # reliable for SFTP: directories such as /etc usually do not end in /.
        # For manually constructed path-only models, retain the trailing slash
        # convenience used by tests and import helpers.
        if self.path.endswith('/') and self.file_type == FileType.FILE:
            self.file_type = FileType.DIRECTORY
    
    def is_directory(self) -> bool:
        """Check if this is a directory."""
        return self.file_type == FileType.DIRECTORY
    
    def is_file(self) -> bool:
        """Check if this is a file."""
        return self.file_type == FileType.FILE
    
    def get_extension(self) -> str:
        """Get file extension."""
        if self.is_file():
            return self.name.split('.')[-1] if '.' in self.name else ''
        return ''