"""Dark theme stylesheet for OpenAdminDesk.

Usage:
    from openadmindesk.ui.theme import apply_theme
    apply_theme(app)
"""

from __future__ import annotations

# ── Color Palette ────────────────────────────────────────────────────────────
# Backgrounds
BG_PRIMARY = "#1e1e1e"       # Main window, panels
BG_SECONDARY = "#252526"     # Tree, sidebar
BG_TERTIARY = "#2d2d30"      # Toolbar, tab bar
BG_INPUT = "#3c3c3c"         # Line edits, text areas
BG_HOVER = "#2a2d2e"         # Hover state
BG_SELECTED = "#094771"      # Selected item background
BG_MENU = "#2d2d30"          # Dropdown menus

# Text
TEXT_PRIMARY = "#cccccc"     # Main text
TEXT_SECONDARY = "#969696"   # Secondary / placeholder
TEXT_DISABLED = "#5a5a5a"    # Disabled text

# Accents
ACCENT_BLUE = "#007acc"      # Primary accent (buttons, selections)
ACCENT_BLUE_HOVER = "#1c97ea"
ACCENT_BLUE_PRESSED = "#005a9e"

# Status
STATUS_GREEN = "#4ec94e"     # Connected, success
STATUS_ORANGE = "#dcaa3a"    # Connecting, warning
STATUS_RED = "#e05555"       # Disconnected, error

# Borders
BORDER = "#3e3e3e"
BORDER_FOCUS = "#007acc"

# Terminal specific
TERMINAL_BG = "#0c0c0c"
TERMINAL_FG = "#00cc00"


DARK_THEME_QSS = f"""
/* ── Global ────────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}}

QMainWindow {{
    background-color: {BG_PRIMARY};
}}

QMainWindow::separator {{
    background-color: {BORDER};
    width: 1px;
    height: 1px;
}}

/* ── Menu Bar ──────────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {BG_TERTIARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
    margin: 1px 2px;
}}

QMenuBar::item:selected {{
    background-color: {BG_HOVER};
}}

QMenuBar::item:pressed {{
    background-color: {BG_SELECTED};
}}

/* ── Menus ─────────────────────────────────────────────────────────────────── */
QMenu {{
    background-color: {BG_MENU};
    border: 1px solid {BORDER};
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 30px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {BG_SELECTED};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ── Toolbar ───────────────────────────────────────────────────────────────── */
QToolBar {{
    background-color: {BG_TERTIARY};
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 3px 6px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {BORDER};
    margin: 0 4px;
}}

QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
}}

QToolButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER};
}}

QToolButton:pressed, QToolButton:checked {{
    background-color: {BG_SELECTED};
    border-color: {ACCENT_BLUE};
}}

QToolButton:disabled {{
    color: {TEXT_DISABLED};
}}

/* ── Push Buttons ──────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 16px;
    color: {TEXT_PRIMARY};
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {ACCENT_BLUE};
}}

QPushButton:pressed {{
    background-color: {BG_SELECTED};
}}

QPushButton:disabled {{
    background-color: {BG_SECONDARY};
    color: {TEXT_DISABLED};
    border-color: {BORDER};
}}

QPushButton:checked {{
    background-color: {BG_SELECTED};
    border-color: {ACCENT_BLUE};
}}

/* ── Line Edit ─────────────────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {BG_SELECTED};
    selection-color: {TEXT_PRIMARY};
}}

QLineEdit:focus {{
    border-color: {ACCENT_BLUE};
}}

QLineEdit:disabled {{
    background-color: {BG_SECONDARY};
    color: {TEXT_DISABLED};
}}

QLineEdit::placeholder {{
    color: {TEXT_SECONDARY};
}}

/* ── Plain Text Edit / Terminal ────────────────────────────────────────────── */
QPlainTextEdit {{
    background-color: {TERMINAL_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 8px;
    color: {TERMINAL_FG};
    selection-background-color: {BG_SELECTED};
    selection-color: {TEXT_PRIMARY};
}}

/* ── Tree Widget ───────────────────────────────────────────────────────────── */
QTreeWidget {{
    background-color: {BG_SECONDARY};
    border: none;
    outline: none;
    color: {TEXT_PRIMARY};
}}

QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 4px;
    margin: 1px 4px;
}}

QTreeWidget::item:hover {{
    background-color: {BG_HOVER};
}}

QTreeWidget::item:selected {{
    background-color: {BG_SELECTED};
    color: {TEXT_PRIMARY};
}}

QTreeWidget::branch {{
    background-color: {BG_SECONDARY};
}}

QTreeWidget::branch:open {{
    image: none;
    border: none;
}}

QTreeWidget::branch:closed:has-children {{
    border: none;
    image: none;
}}

QTreeWidget QHeaderView::section {{
    background-color: {BG_TERTIARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-weight: bold;
    font-size: 12px;
}}

/* ── Splitter ──────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* ── Tab Widget ────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_PRIMARY};
}}

QTabBar::tab {{
    background-color: {BG_SECONDARY};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    margin-right: 2px;
    color: {TEXT_SECONDARY};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

QTabBar::tab:selected {{
    background-color: {BG_PRIMARY};
    border-bottom: 2px solid {ACCENT_BLUE};
    color: {TEXT_PRIMARY};
}}

QTabBar::close-button {{
    image: none;
    border: none;
    border-radius: 4px;
    padding: 2px;
}}

QTabBar::close-button:hover {{
    background-color: {STATUS_RED};
}}

/* ── Status Bar ────────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_TERTIARY};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    padding: 2px 8px;
    font-size: 12px;
}}

/* ── Table Widget ───────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    color: {TEXT_PRIMARY};
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected {{
    background-color: {BG_SELECTED};
    color: {TEXT_PRIMARY};
}}

QTableWidget QHeaderView::section {{
    background-color: {BG_TERTIARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-weight: bold;
    font-size: 12px;
}}

/* ── Combo Box ─────────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    min-width: 80px;
}}

QComboBox:hover {{ border-color: {ACCENT_BLUE}; }}
QComboBox:focus {{ border-color: {ACCENT_BLUE}; }}

QComboBox::drop-down {{
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    border-left: 1px solid {BORDER};
}}

QComboBox QAbstractItemView {{
    background-color: {BG_MENU};
    border: 1px solid {BORDER};
    selection-background-color: {BG_SELECTED};
    selection-color: {TEXT_PRIMARY};
}}

/* ── Dialog ────────────────────────────────────────────────────────────────── */
QDialog {{
    background-color: {BG_PRIMARY};
}}

/* ── Tool Tips ─────────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_TERTIARY};
    border: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}}

/* ── Scroll Bars ───────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: {BG_PRIMARY};
    width: 10px;
    margin: 0;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #424242;
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #555555;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
}}

QScrollBar:horizontal {{
    background-color: {BG_PRIMARY};
    height: 10px;
    margin: 0;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #424242;
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #555555;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
}}
"""


def apply_theme(app) -> None:
    """Apply the dark theme to the entire QApplication.

    Args:
        app: QApplication instance.
    """
    app.setStyleSheet(DARK_THEME_QSS)
