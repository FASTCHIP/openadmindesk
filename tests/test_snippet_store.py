"""Tests for snippet store."""

import tempfile
import os
from openadmindesk.core.snippet_store import SnippetStore, Snippet


def test_snippet_store_creation() -> None:
    """Snippet store creates with empty state."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        file_path = tmp.name
    
    try:
        store = SnippetStore(file_path)
        assert store is not None
        assert store.get_all_snippets() == []
        assert store.get_snippet("nonexistent") is None
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)


def test_snippet_store_operations() -> None:
    """Test snippet store operations."""
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        file_path = tmp.name
    
    try:
        store = SnippetStore(file_path)
        
        # Add a snippet
        snippet = Snippet(
            id="test1",
            name="Test Snippet",
            content="echo 'hello world'",
            language="bash"
        )
        
        success = store.add_snippet(snippet)
        assert success
        
        # Get the snippet
        retrieved = store.get_snippet("test1")
        assert retrieved is not None
        assert retrieved.name == "Test Snippet"
        
        # Get all snippets
        snippets = store.get_all_snippets()
        assert len(snippets) == 1
        
        # Update the snippet
        snippet.content = "echo 'updated'"
        success = store.update_snippet(snippet)
        assert success
        
        # Verify update
        updated = store.get_snippet("test1")
        assert updated.content == "echo 'updated'"
        
        # Delete the snippet
        success = store.delete_snippet("test1")
        assert success
        
        # Verify deletion
        deleted = store.get_snippet("test1")
        assert deleted is None
        
    finally:
        # Clean up
        if os.path.exists(file_path):
            os.unlink(file_path)