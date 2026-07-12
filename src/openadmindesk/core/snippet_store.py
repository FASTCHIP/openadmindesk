"""Snippet store."""

from __future__ import annotations

import json
import os
import logging
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Snippet:
    """Snippet model."""
    
    id: str
    name: str
    content: str
    language: str = "bash"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SnippetStore:
    """Store for snippets."""
    
    def __init__(self, file_path: str = "snippets.json") -> None:
        """Initialize the snippet store."""
        self.file_path = file_path
        self._snippets: List[Snippet] = []
        self._load_snippets()
    
    def _load_snippets(self) -> None:
        """Load snippets from file."""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                
                # Convert to Snippet objects
                self._snippets = [
                    Snippet(**snippet_data) for snippet_data in data
                ]
        except Exception as e:
            logger.error(f"Failed to load snippets from {self.file_path}: {e}")
            self._snippets = []
    
    def _save_snippets(self) -> None:
        """Save snippets to file."""
        try:
            # Convert to dict
            data = [snippet.__dict__ for snippet in self._snippets]
            
            # Save to file
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save snippets to {self.file_path}: {e}")
    
    def add_snippet(self, snippet: Snippet) -> bool:
        """Add a snippet."""
        try:
            self._snippets.append(snippet)
            self._save_snippets()
            return True
        except Exception:
            return False
    
    def get_snippet(self, snippet_id: str) -> Optional[Snippet]:
        """Get a snippet by ID."""
        for snippet in self._snippets:
            if snippet.id == snippet_id:
                return snippet
        return None
    
    def get_all_snippets(self) -> List[Snippet]:
        """Get all snippets."""
        return self._snippets.copy()
    
    def update_snippet(self, snippet: Snippet) -> bool:
        """Update a snippet."""
        try:
            for i, s in enumerate(self._snippets):
                if s.id == snippet.id:
                    self._snippets[i] = snippet
                    self._save_snippets()
                    return True
            return False
        except Exception:
            return False
    
    def delete_snippet(self, snippet_id: str) -> bool:
        """Delete a snippet."""
        try:
            for i, snippet in enumerate(self._snippets):
                if snippet.id == snippet_id:
                    self._snippets.pop(i)
                    self._save_snippets()
                    return True
            return False
        except Exception:
            return False