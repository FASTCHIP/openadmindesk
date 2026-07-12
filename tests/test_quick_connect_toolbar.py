"""Tests for quick connect toolbar."""

from openadmindesk.ui.quick_connect_toolbar import QuickConnectToolbar


def test_quick_connect_toolbar_emits_trimmed_host() -> None:
    toolbar = QuickConnectToolbar()
    seen: list[str] = []
    toolbar.connect_requested.connect(seen.append)

    toolbar.host_input.setText("  admin@example.com:22  ")
    toolbar._on_connect()

    assert seen == ["admin@example.com:22"]


def test_quick_connect_toolbar_ignores_empty_host() -> None:
    toolbar = QuickConnectToolbar()
    seen: list[str] = []
    toolbar.connect_requested.connect(seen.append)

    toolbar.host_input.setText("   ")
    toolbar._on_connect()

    assert seen == []
