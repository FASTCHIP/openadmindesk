"""Snippet inserter for terminals."""

from __future__ import annotations

from typing import Optional
from openadmindesk.core.snippet_store import SnippetStore
from openadmindesk.core.terminal_backend import TerminalBackend


class SnippetInserter:
    """Inserts snippets into terminals."""
    
    def __init__(self, snippet_store: SnippetStore) -> None:
        """Initialize the snippet inserter."""
        self.snippet_store = snippet_store
    
    def insert_snippet(self, snippet_id: str, terminal: TerminalBackend) -> bool:
        """Insert a snippet into a terminal."""
        # Get the snippet
        snippet = self.snippet_store.get_snippet(snippet_id)
        if not snippet:
            return False
        
        # Insert into terminal
        try:
            # For now, just write the snippet content
            terminal.write(snippet.content + "\n")
            return True
        except Exception:
            return False
    
    def insert_snippet_at_cursor(self, snippet_id: str, terminal: TerminalBackend, 
                                cursor_position: int) -> bool:
        """Insert a snippet at a specific cursor position."""
        # This would require more complex terminal handling
        # For now, just insert at end
        return self.insert_snippet(snippet_id, terminal)
    
    def get_snippet_preview(self, snippet_id: str) -> Optional[str]:
        """Get a preview of a snippet."""
        snippet = self.snippet_store.get_snippet(snippet_id)
        if snippet:
            # Return first few lines of content
            lines = snippet.content.split('\n')
            return '\n'.join(lines[:3]) + ('...' if len(lines) > 3 else '')
        return None