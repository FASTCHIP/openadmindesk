"""Terminal backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Optional


class TerminalBackend(ABC):
    """Abstract base class for terminal backends."""
    
    @abstractmethod
    def connect(self, on_output: Optional[Callable[[bytes], None]] = None) -> bool:
        """Connect using this backend's configured profile/session context."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the remote host."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
    
    @abstractmethod
    def write(self, data: str) -> None:
        """Write data to the terminal."""
        pass
    
    @abstractmethod
    def read(self, size: int = 1024) -> str:
        """Read data from the terminal."""
        pass
    
    @abstractmethod
    def get_pid(self) -> Optional[int]:
        """Get the process ID of the terminal."""
        pass
    
    @abstractmethod
    def get_connection_info(self) -> dict:
        """Get connection information."""
        pass
    
    @abstractmethod
    def set_size(self, rows: int, cols: int) -> None:
        """Set terminal size."""
        pass
    
    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        """Get terminal size."""
        pass