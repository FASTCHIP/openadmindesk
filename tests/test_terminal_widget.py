"""Tests for terminal widget — the core pyte-based terminal emulator."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from openadmindesk.ui.terminal_theme import build_matrix_theme
from openadmindesk.ui.terminal_widget import TerminalWidget


def test_terminal_widget_creation(qapp) -> None:
    """Terminal widget can be created with defaults."""
    term = TerminalWidget(columns=80, rows=24)
    assert term is not None
    assert term.theme is not None
    assert term.theme.name == "Dark"


def test_terminal_widget_feed_basic(qapp) -> None:
    """Feeding text into the terminal should update the screen."""
    term = TerminalWidget(columns=80, rows=24)
    term.feed("Hello, World!")
    screen_text = "".join(
        term.screen.buffer[0][i].data for i in range(min(13, 80))
    )
    assert "Hello" in screen_text


def test_terminal_widget_clear(qapp) -> None:
    """Clear should reset the screen."""
    term = TerminalWidget(columns=80, rows=24)
    term.feed("Some text")
    term.clear()
    assert term.screen.buffer[0][0].data == " "


def test_terminal_widget_theme_switch(qapp) -> None:
    """Switching theme should update colors."""
    term = TerminalWidget(columns=80, rows=24)
    matrix = build_matrix_theme()
    term.set_theme(matrix)
    assert term.theme.name == "Matrix"
    assert term.theme.background == "#000000"


def test_terminal_widget_opacity_change(qapp) -> None:
    """Background opacity should be settable."""
    term = TerminalWidget(columns=80, rows=24)
    term.set_bg_opacity(128)
    assert term.theme.bg_opacity == 128


def test_terminal_widget_no_selection_by_default(qapp) -> None:
    """Initially there should be no selected text."""
    term = TerminalWidget(columns=80, rows=24)
    assert term.get_selected_text() == ""


def test_terminal_widget_resize_screen(qapp) -> None:
    """Resizing should update the screen dimensions."""
    term = TerminalWidget(columns=80, rows=24)
    term.resize_screen(120, 40)
    assert term.screen.columns == 120
    assert term.screen.lines == 40


def test_terminal_widget_scrollback(qapp) -> None:
    """Feeding more lines than screen height should capture scrollback."""
    term = TerminalWidget(columns=80, rows=5)  # small screen
    for i in range(8):
        term.feed(f"Line {i}\r\n")
    assert len(term._scrollback) > 0
    assert "Line 0" in term._scrollback[0]
    assert term._scroll_position == 0  # starts at live view


def test_terminal_widget_scroll_history(qapp) -> None:
    """Scrolling up should change scroll position."""
    term = TerminalWidget(columns=80, rows=5)
    for i in range(10):
        term.feed(f"Line {i}\r\n")
    term._scroll_position = 3
    assert term._scroll_position == 3


def test_terminal_widget_reset_scroll(qapp) -> None:
    """Resetting scroll should go back to live view."""
    term = TerminalWidget(columns=80, rows=5)
    for i in range(10):
        term.feed(f"Line {i}\r\n")
    term._scroll_position = 3
    term._reset_scroll_position()
    assert term._scroll_position == 0

def test_terminal_widget_sgr_color_escape(qapp) -> None:
    """ANSI SGR color sequences should update pyte character attributes."""
    term = TerminalWidget(columns=20, rows=5)

    term.feed("\x1b[31mR")

    char = term.screen.buffer[0][0]
    assert char.data == "R"
    assert char.fg == "red"


def test_terminal_widget_cursor_position_escape(qapp) -> None:
    """Cursor-position escapes should place following text at the target cell."""
    term = TerminalWidget(columns=20, rows=5)

    term.feed("\x1b[3;5HX")

    assert term.screen.buffer[2][4].data == "X"


def test_terminal_widget_clear_screen_escape(qapp) -> None:
    """Clear-screen escapes should clear previous terminal content."""
    term = TerminalWidget(columns=20, rows=5)

    term.feed("hello")
    term.feed("\x1b[2J")

    assert all(
        term.screen.buffer[row][col].data == " "
        for row in range(term.screen.lines)
        for col in range(term.screen.columns)
    )


def test_terminal_widget_key_press_emits_terminal_text(qapp) -> None:
    term = TerminalWidget(columns=20, rows=5)
    seen = []
    term.key_pressed.connect(seen.append)

    term.keyPressEvent(
        QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a")
    )
    term.keyPressEvent(
        QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r")
    )

    assert seen == ["a", "\r"]
