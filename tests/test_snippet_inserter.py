"""Tests for snippet inserter."""

from dataclasses import dataclass
from unittest.mock import Mock

from openadmindesk.core.snippet_store import SnippetStore
from openadmindesk.core.snippet_inserter import SnippetInserter


@dataclass
class FakeSnippet:
    content: str


class FakeTerminal:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, data: str) -> None:
        self.writes.append(data)


def test_snippet_inserter_writes_snippet_and_returns_preview() -> None:
    store = Mock(spec=SnippetStore)
    store.get_snippet.return_value = FakeSnippet("one\ntwo\nthree\nfour")
    inserter = SnippetInserter(store)
    terminal = FakeTerminal()

    assert inserter.insert_snippet("snippet-1", terminal) is True
    assert terminal.writes == ["one\ntwo\nthree\nfour\n"]
    assert inserter.insert_snippet_at_cursor("snippet-1", terminal, 3) is True
    assert terminal.writes[-1] == "one\ntwo\nthree\nfour\n"
    assert inserter.get_snippet_preview("snippet-1") == "one\ntwo\nthree..."


def test_snippet_inserter_handles_missing_snippet() -> None:
    store = Mock(spec=SnippetStore)
    store.get_snippet.return_value = None
    inserter = SnippetInserter(store)
    terminal = FakeTerminal()

    assert inserter.insert_snippet("missing", terminal) is False
    assert inserter.get_snippet_preview("missing") is None
    assert terminal.writes == []
