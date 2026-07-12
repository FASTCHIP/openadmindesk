"""Pure-Python terminal emulator widget using pyte — with theme support."""

from __future__ import annotations

import pyte
from PySide6.QtWidgets import QWidget, QApplication, QLineEdit
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QKeyEvent, QMouseEvent, QFont, QPen
from PySide6.QtCore import Qt, QTimer, QRect, Signal, QPoint, QEvent
from typing import Optional, Tuple
import re
import webbrowser

from openadmindesk.ui.terminal_theme import TerminalTheme, build_dark_theme
from openadmindesk.core.l10n import _

# ANSI color name indices (pyte uses these)
_URL_RE = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


class TerminalWidget(QWidget):
    """A widget that renders a pyte Screen using QPainter.

    Supports theme switching, font changes, and background opacity.
    """

    key_pressed = Signal(str)

    def __init__(self, columns: int = 80, rows: int = 24, parent=None) -> None:
        super().__init__(parent)
        self._screen = pyte.Screen(columns, rows)
        self._stream = pyte.Stream(self._screen)
        self._cursor_visible = True

        # Selection state
        self._selecting = False
        self._sel_start: Optional[Tuple[int, int]] = None  # (col, row) in screen coords
        self._sel_end: Optional[Tuple[int, int]] = None

        # Theme
        self._theme = build_dark_theme()
        self._colors: dict[str, QColor] = {}
        self._bg = QColor(self._theme.background)
        self._fg = QColor(self._theme.foreground)
        self._cursor_qc = QColor(self._theme.cursor)
        self._font = self._theme.to_font()
        self._build_color_cache()

        # Metrics
        self._fm = QFontMetrics(self._font)
        self._char_width = self._fm.horizontalAdvance("W")
        self._char_height = self._fm.height()

        self.setMinimumSize(400, 200)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        # Disable system input method (IBus/fcitx) — terminal needs raw keys
        self.setAttribute(Qt.WA_InputMethodEnabled, False)
        self._ime_disabled = True

        # Blinking cursor
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._toggle_cursor)
        self._cursor_timer.start(530)

        # ── scrollback ─────────────────────────────────────────────────────
        self._scrollback: list[str] = []        # lines that scrolled off the screen
        self._scroll_position = 0               # 0 = live view, >0 = scrolled up
        self._max_scrollback = 5000
        self._prev_top_line = ""                # previous content of line 0 for scroll detection

        # ── search ─────────────────────────────────────────────────────────
        self._search_bar = QLineEdit(self)
        self._search_bar.setPlaceholderText(_("Find in terminal..."))
        self._search_bar.setVisible(False)
        self._search_bar.setStyleSheet(
            "background-color: #252526; color: #cccccc; border: 1px solid #007acc;"
            "border-radius: 3px; padding: 3px 6px; font-size: 12px;"
        )
        self._search_bar.textChanged.connect(self._do_search)
        self._search_bar.returnPressed.connect(self._search_next)
        self._search_bar.installEventFilter(self)
        self._search_matches: list[tuple[int, int, int]] = []
        self._current_match = -1

    # ── theme / appearance ────────────────────────────────────────────────────

    def _build_color_cache(self) -> None:
        """Pre-compute QColor objects from theme hex strings."""
        self._colors = {k: QColor(v) for k, v in self._theme.__dict__.items()
                        if isinstance(v, str) and v.startswith("#")}
        self._bg = QColor(self._theme.background)
        self._bg.setAlpha(self._theme.bg_opacity)
        self._fg = QColor(self._theme.foreground)
        self._cursor_qc = QColor(self._theme.cursor)

    def set_theme(self, theme: TerminalTheme) -> None:
        """Apply a new theme."""
        self._theme = theme
        self._build_color_cache()
        self._font = theme.to_font()
        self._fm = QFontMetrics(self._font)
        self._char_width = self._fm.horizontalAdvance("W")
        self._char_height = self._fm.height()
        self.update()

    def set_font(self, family: str, size: int) -> None:
        """Change font without changing colors."""
        self._theme.font_family = family
        self._theme.font_size = size
        self._font = self._theme.to_font()
        self._fm = QFontMetrics(self._font)
        self._char_width = self._fm.horizontalAdvance("W")
        self._char_height = self._fm.height()
        self.update()

    def set_bg_opacity(self, opacity: int) -> None:
        """Set background opacity (0-255)."""
        self._theme.bg_opacity = max(0, min(255, opacity))
        self._bg.setAlpha(self._theme.bg_opacity)
        self.update()

    @property
    def theme(self) -> TerminalTheme:
        return self._theme

    # ── public API ────────────────────────────────────────────────────────────

    def feed(self, data: str) -> None:
        """Feed data (ANSI-encoded) into the terminal. Captures scrollback."""
        # Snapshot line 0 before scroll
        self._prev_top_line = "".join(
            self._screen.buffer[0][i].data for i in range(self._screen.columns)
        ) if self._screen.lines > 0 else ""

        self._stream.feed(data)

        # After feed: if cursor is on the last line and line 0 changed,
        # content scrolled off — capture it
        if self._screen.lines > 0:
            new_top = "".join(
                self._screen.buffer[0][i].data for i in range(self._screen.columns)
            )
            # If line 0 was previously non-empty and changed, it scrolled off
            # Also check if cursor filled the screen (cursor.y at bottom)
            if self._prev_top_line.strip() and self._prev_top_line != new_top:
                self._scrollback.append(self._prev_top_line.rstrip())
                if len(self._scrollback) > self._max_scrollback:
                    self._scrollback.pop(0)

        self.update()

    def resize_screen(self, columns: int, rows: int) -> None:
        self._screen.resize(rows, columns)
        self.update()

    def clear(self) -> None:
        self._screen.reset()
        self.update()

    @property
    def screen(self) -> pyte.Screen:
        return self._screen

    # ── rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Fill background with opacity
        painter.fillRect(self.rect(), self._bg)

        # Paint selection highlight
        self._paint_selection(painter)

        # Paint search matches
        self._paint_search_matches(painter)

        # Visible lines (follow cursor / scroll)
        cursor_y = self._screen.cursor.y
        visible_count = self.visible_rows()
        top = max(0, cursor_y - visible_count + 1) if cursor_y >= visible_count else 0

        default_bg = QColor(self._theme.background)

        # Determine source of visible lines
        if self._scroll_position > 0:
            # Show from scrollback
            sb = self._scrollback
            scroll_from = max(0, len(sb) - self._scroll_position)
            for row_idx in range(visible_count):
                sb_index = scroll_from + row_idx
                if sb_index < len(sb):
                    # Render scrollback line as plain text (no ANSI color info)
                    line_text = sb[sb_index]
                    y = row_idx * self._char_height
                    painter.setPen(self._fg)
                    painter.drawText(QRect(0, y, self.width(), self._char_height),
                                     Qt.AlignLeft | Qt.AlignTop, line_text)
                else:
                    # Show buffer lines
                    screen_row = row_idx - (visible_count - (len(sb) - scroll_from))
                    if 0 <= screen_row < self._screen.lines:
                        self._render_line(painter, screen_row, row_idx, default_bg)
            # Paint "scrollback" indicator overlay
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.width() - 60, self._char_height + 2,
                             f"↑ {self._scroll_position}")
        else:
            # Normal live view
            visible_lines = range(top, min(top + visible_count, self._screen.lines))
            for row_idx, screen_row in enumerate(visible_lines):
                self._render_line(painter, screen_row, row_idx, default_bg)

        # Cursor (only in live view)
        if self._scroll_position == 0 and self._cursor_visible and self.hasFocus():
            self._draw_cursor(painter)

        painter.end()

    def _render_line(self, painter: QPainter, screen_row: int, vis_row: int,
                     default_bg: QColor) -> None:
        """Render one screen line from the buffer at the given visual row."""
        if screen_row >= self._screen.lines:
            return
        y = vis_row * self._char_height
        x = 0
        line = self._screen.buffer[screen_row]
        cols = min(self._screen.columns, len(line))

        base_font = self._font
        bold_font = QFont(base_font)
        bold_font.setBold(True)
        italic_font = QFont(base_font)
        italic_font.setItalic(True)
        bold_italic_font = QFont(base_font)
        bold_italic_font.setBold(True)
        bold_italic_font.setItalic(True)

        for col_idx in range(cols):
            char_data = line[col_idx]
            char = char_data.data
            fg = self._fg_color(char_data.fg)
            bg = self._bg_color(char_data.bg)

            cell_rect = QRect(x, y, self._char_width, self._char_height)

            if bg != default_bg:
                painter.fillRect(cell_rect, bg)

            if char and char != " ":
                # Apply font styles
                if char_data.bold and char_data.italics:
                    painter.setFont(bold_italic_font)
                elif char_data.bold:
                    painter.setFont(bold_font)
                elif char_data.italics:
                    painter.setFont(italic_font)
                else:
                    painter.setFont(base_font)

                painter.setPen(fg)
                painter.drawText(cell_rect, Qt.AlignLeft | Qt.AlignTop, char)

                # Underline
                if char_data.underscore:
                    painter.setPen(QPen(fg, 1))
                    painter.drawLine(
                        x, y + self._char_height - 2,
                        x + self._char_width, y + self._char_height - 2
                    )
                # Strikethrough
                if char_data.strikethrough:
                    painter.setPen(QPen(fg, 1))
                    painter.drawLine(
                        x, y + self._char_height // 2,
                        x + self._char_width, y + self._char_height // 2
                    )

            x += self._char_width

        # Restore base font
        painter.setFont(base_font)

    def _fg_color(self, attr) -> QColor:
        """Map pyte foreground colour (str in 0.8+) to QColor."""
        if attr == "default" or not attr:
            return self._fg
        return self._colors.get(attr, self._fg)

    def _bg_color(self, attr) -> QColor:
        """Map pyte background colour (str in 0.8+) to QColor."""
        if attr == "default" or not attr:
            return self._bg
        return self._colors.get(attr, self._bg)

    def _draw_cursor(self, painter: QPainter) -> None:
        cursor = self._screen.cursor
        visible_count = self.visible_rows()
        display_top = max(0, cursor.y - visible_count + 1) if cursor.y >= visible_count else 0
        row = cursor.y - display_top
        x = cursor.x * self._char_width
        y = row * self._char_height
        cell = QRect(x, y, self._char_width, self._char_height)

        painter.fillRect(cell, self._cursor_qc)
        # Invert character on cursor
        line = self._screen.buffer[cursor.y]
        if cursor.x < len(line):
            char = line[cursor.x].data
            if char:
                painter.setPen(self._bg)
                painter.drawText(cell, Qt.AlignLeft | Qt.AlignTop, char)

    # ── input handling is implemented near the bottom with search/scrollback shortcuts.

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    # ── sizing ────────────────────────────────────────────────────────────────

    def visible_columns(self) -> int:
        return max(1, self.width() // self._char_width)

    def visible_rows(self) -> int:
        return max(1, self.height() // self._char_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.setAttribute(
            Qt.WA_OpaquePaintEvent,
            self._theme.bg_opacity >= 255,
        )
        cols = self.visible_columns()
        rows = self.visible_rows()
        if cols != self._screen.columns or rows != self._screen.lines:
            self.resize_screen(cols, rows)
        # Position search bar at bottom
        sb = self._search_bar
        sbh = 24  # search bar height
        sb.setGeometry(0, self.height() - sbh - 2, self.width(), sbh)

    def eventFilter(self, obj, event) -> bool:
        """Handle key events in search bar."""
        if obj == self._search_bar and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._toggle_search()
                return True
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if event.modifiers() == Qt.ShiftModifier:
                    # Shift+Enter → previous match
                    if self._search_matches:
                        self._current_match = (self._current_match - 1) % len(self._search_matches)
                        self.update()
                    return True
                else:
                    self._search_next()
                    return True
        return super().eventFilter(obj, event)

    # ── mouse selection ───────────────────────────────────────────────────────

    def _char_at_pos(self, pos: QPoint) -> Tuple[int, int]:
        """Convert pixel position to (col, row) in visible screen coordinates."""
        col = max(0, pos.x() // self._char_width)
        row = max(0, pos.y() // self._char_height)
        return (col, row)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus(Qt.MouseFocusReason)
        if event.button() == Qt.LeftButton:
            # Click returns to live view
            if self._scroll_position > 0:
                self._reset_scroll_position()

            # Ctrl+Click → open URL
            if event.modifiers() == Qt.ControlModifier:
                url = self._url_at_pos(event.pos())
                if url:
                    webbrowser.open(url)
                    return

            self._selecting = True
            col, row = self._char_at_pos(event.pos())
            self._sel_start = (col, row)
            self._sel_end = (col, row)
            self.update()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._selecting:
            col, row = self._char_at_pos(event.pos())
            self._sel_end = (col, row)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            # Copy to selection clipboard (middle-click paste on Linux)
            text = self.get_selected_text()
            if text:
                clipboard = QApplication.clipboard()
                clipboard.setText(text)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Select word under cursor on double-click."""
        col, row = self._char_at_pos(event.pos())
        if row < self._screen.lines:
            line = self._screen.buffer[row]
            if col < len(line):
                text = ""
                for i in range(col, len(line)):
                    if line[i].data and line[i].data != " ":
                        text += line[i].data
                    else:
                        break
                self._sel_start = (col, row)
                self._sel_end = (col + len(text), row)
                self.update()

    def get_selected_text(self) -> str:
        """Return the currently selected text."""
        if not self._sel_start or not self._sel_end:
            return ""
        c1, r1 = self._sel_start
        c2, r2 = self._sel_end

        if r1 > r2 or (r1 == r2 and c1 > c2):
            c1, c2 = c2, c1
            r1, r2 = r2, r1

        lines = []
        for r in range(r1, r2 + 1):
            if r >= self._screen.lines:
                break
            line = self._screen.buffer[r]
            start_col = c1 if r == r1 else 0
            end_col = c2 + 1 if r == r2 else len(line)
            chars = [line[i].data for i in range(start_col, min(end_col, len(line)))]
            lines.append("".join(chars))
        return "\n".join(lines)

    def _paint_selection(self, painter: QPainter) -> None:
        """Paint text selection highlight."""
        if not self._sel_start or not self._sel_end:
            return

        c1, r1 = self._sel_start
        c2, r2 = self._sel_end
        if r1 > r2 or (r1 == r2 and c1 > c2):
            c1, c2 = c2, c1
            r1, r2 = r2, r1

        visible_count = self.visible_rows()
        cursor_y = self._screen.cursor.y
        display_top = max(0, cursor_y - visible_count + 1) if cursor_y >= visible_count else 0

        highlight = QColor(38, 79, 120, 120)

        for r in range(r1, r2 + 1):
            vis_row = r - display_top
            if vis_row < 0 or vis_row >= visible_count:
                continue
            start_col = c1 if r == r1 else 0
            end_col = c2 + 1 if r == r2 else self._screen.columns
            x = start_col * self._char_width
            y = vis_row * self._char_height
            painter.fillRect(QRect(x, y, (end_col - start_col) * self._char_width, self._char_height), highlight)

    def _select_all(self) -> None:
        self._sel_start = (0, 0)
        last_row = max(0, self._screen.lines - 1)
        line = self._screen.buffer[last_row]
        last_col = max(0, len(line) - 1) if line else 0
        self._sel_end = (last_col, last_row)
        self.update()

    def _url_at_pos(self, pos: QPoint) -> Optional[str]:
        """Find a URL under the given pixel position."""
        col, row = self._char_at_pos(pos)
        if row >= self._screen.lines:
            return None
        line = self._screen.buffer[row]
        text = "".join(ch.data for ch in line if ch.data)
        for m in _URL_RE.finditer(text):
            if m.start() <= col < m.end():
                return m.group()
        return None

    def _copy_selection(self) -> None:
        text = self.get_selected_text()
        if text:
            QApplication.clipboard().setText(text)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.key_pressed.emit(text)

    def _select_all(self) -> None:
        self._sel_start = (0, 0)
        last_row = max(0, len(self._screen.display) - 1)
        last_col = max(0, len(self._screen.display[last_row]) - 1) if self._screen.display else 0
        self._sel_end = (last_col, last_row)
        self.update()

    def _toggle_ime(self) -> None:
        """Toggle system input method on/off for this terminal."""
        self._ime_disabled = not self._ime_disabled
        self.setAttribute(Qt.WA_InputMethodEnabled, not self._ime_disabled)

    # ── mouse wheel / scrollback ──────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel — scroll through history."""
        delta = event.angleDelta().y()
        if delta > 0:
            # Scroll up
            self._scroll_position = min(
                self._scroll_position + 1,
                len(self._scrollback)
            )
        elif delta < 0 and self._scroll_position > 0:
            # Scroll down toward live view
            self._scroll_position -= 1
        self.update()

    def _reset_scroll_position(self) -> None:
        """Return to live view (bottom of output)."""
        self._scroll_position = 0
        self.update()

    # ── search ─────────────────────────────────────────────────────────────────

    def _toggle_search(self) -> None:
        """Show/hide the search bar."""
        visible = not self._search_bar.isVisible()
        self._search_bar.setVisible(visible)
        if visible:
            self._search_bar.setFocus()
            self._search_bar.selectAll()
        else:
            self._search_matches.clear()
            self._current_match = -1
            self.setFocus()
        self.update()

    def _do_search(self, text: str) -> None:
        """Find all matches in live buffer and scrollback."""
        self._search_matches.clear()
        self._current_match = -1
        if not text:
            self.update()
            return

        text_lower = text.lower()
        # Search in all buffer rows
        for row_idx in range(self._screen.lines):
            line_text = "".join(
                self._screen.buffer[row_idx][c].data
                for c in range(self._screen.columns)
            ).lower()
            self._find_in_line(text_lower, line_text, row_idx)

        # Search in scrollback (as virtual rows before buffer)
        for sb_idx, sb_line in enumerate(self._scrollback):
            virtual_row = -(sb_idx + 1)  # negative = scrollback
            self._find_in_line(text_lower, sb_line.lower(), virtual_row, sb_line)

        if self._search_matches:
            self._current_match = 0
        self.update()

    def _find_in_line(self, text: str, line_text: str, row: int,
                      raw_line: str = None) -> None:
        """Find all occurrences of text in a line."""
        start = 0
        while True:
            pos = line_text.find(text, start)
            if pos == -1:
                break
            self._search_matches.append((row, pos, pos + len(text)))
            start = pos + 1

    def _search_next(self) -> None:
        """Go to the next search match."""
        if not self._search_matches:
            return
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ShiftModifier:
            # Shift+Enter → previous
            self._current_match = (self._current_match - 1) % len(self._search_matches)
        else:
            self._current_match = (self._current_match + 1) % len(self._search_matches)
        self.update()

    def _paint_search_matches(self, painter: QPainter) -> None:
        """Highlight search matches."""
        if not self._search_matches:
            return

        cursor_y = self._screen.cursor.y
        visible_count = self.visible_rows()
        top = max(0, cursor_y - visible_count + 1) if cursor_y >= visible_count else 0

        highlight = QColor(255, 255, 0, 80)   # yellow semi-transparent
        current_hl = QColor(255, 165, 0, 120)  # orange for current match

        for idx, (row, c_start, c_end) in enumerate(self._search_matches):
            # Map row to visible position
            if row >= 0:
                # Buffer row
                vis_row = row - top
                if vis_row < 0 or vis_row >= visible_count:
                    # Check if in scrollback area
                    if self._scroll_position > 0 and self._scroll_position >= row:
                        continue
                    continue
            else:
                # Scrollback row (negative)
                vis_row = row  # Will be shown from scrollback rendering
                # For now, only highlight live view matches
                continue

            color = current_hl if idx == self._current_match else highlight
            y = vis_row * self._char_height
            x = c_start * self._char_width
            w = (c_end - c_start) * self._char_width
            painter.fillRect(QRect(x, y, w, self._char_height), color)

    # ── keyboard: Ctrl+C copy + scrollback reset ──────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Reset scroll position on any key press
        if self._scroll_position > 0:
            self._reset_scroll_position()

        # Ctrl+Shift+C → copy (terminal-style)
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_C:
            self._copy_selection()
            return
        # Ctrl+Shift+V → paste
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_V:
            self._paste_clipboard()
            return
        # Ctrl+F → toggle search
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_F:
            self._toggle_search()
            return
        # Escape → close search (handled in eventFilter)
        if event.key() == Qt.Key_Escape and self._search_bar.isVisible():
            self._toggle_search()
            return

        text = event.text()
        key_map = {
            Qt.Key_Up: "\x1b[A", Qt.Key_Down: "\x1b[B",
            Qt.Key_Right: "\x1b[C", Qt.Key_Left: "\x1b[D",
            Qt.Key_Home: "\x1b[H", Qt.Key_End: "\x1b[F",
            Qt.Key_Backspace: "\x7f", Qt.Key_Delete: "\x1b[3~",
            Qt.Key_Return: "\r", Qt.Key_Enter: "\r",
            Qt.Key_Tab: "\t", Qt.Key_Escape: "\x1b",
            Qt.Key_PageUp: "\x1b[5~", Qt.Key_PageDown: "\x1b[6~",
            Qt.Key_Insert: "\x1b[2~",
            Qt.Key_F1: "\x1bOP", Qt.Key_F2: "\x1bOQ",
            Qt.Key_F3: "\x1bOR", Qt.Key_F4: "\x1bOS",
            Qt.Key_F5: "\x1b[15~", Qt.Key_F6: "\x1b[17~",
            Qt.Key_F7: "\x1b[18~", Qt.Key_F8: "\x1b[19~",
            Qt.Key_F9: "\x1b[20~", Qt.Key_F10: "\x1b[21~",
            Qt.Key_F11: "\x1b[23~", Qt.Key_F12: "\x1b[24~",
        }

        if event.modifiers() == Qt.ControlModifier and text:
            ctrl_char = chr(ord(text.upper()) - 64)
            self.key_pressed.emit(ctrl_char)
            return

        if event.key() in key_map:
            self.key_pressed.emit(key_map[event.key()])
        elif text:
            self.key_pressed.emit(text)
        else:
            super().keyPressEvent(event)
