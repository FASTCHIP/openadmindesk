"""Terminal theme system — presets and custom themes for the terminal emulator."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont

# ── Theme dataclass ───────────────────────────────────────────────────────────


@dataclass
class TerminalTheme:
    """Complete terminal appearance theme."""
    name: str = "Custom"

    # ANSI 16-color palette
    black: str = "#000000"
    red: str = "#cd3131"
    green: str = "#0dbc79"
    yellow: str = "#e5e510"
    blue: str = "#2472c8"
    magenta: str = "#bc3fbc"
    cyan: str = "#11a8cd"
    white: str = "#cccccc"
    bright_black: str = "#666666"
    bright_red: str = "#f14c4c"
    bright_green: str = "#23d18b"
    bright_yellow: str = "#f5f543"
    bright_blue: str = "#3b8eea"
    bright_magenta: str = "#d670d6"
    bright_cyan: str = "#29b8db"
    bright_white: str = "#e5e5e5"

    # Background / foreground
    background: str = "#0c0c0c"
    foreground: str = "#cccccc"
    cursor: str = "#ffffff"

    # Font
    font_family: str = "monospace"
    font_size: int = 10

    # Background opacity (0 = fully transparent, 255 = fully opaque)
    bg_opacity: int = 255

    def to_colors(self) -> dict[str, QColor]:
        """Return all colors as QColor dict."""
        return {
            k: QColor(v) for k, v in self.__dict__.items()
            if isinstance(v, str) and v.startswith("#")
        }

    def to_font(self) -> QFont:
        font = QFont(self.font_family, self.font_size)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        return font


# ── Pre-built themes ──────────────────────────────────────────────────────────


def build_matrix_theme() -> TerminalTheme:
    """Matrix-style theme — green on black with glow-like palette."""
    return TerminalTheme(
        name="Matrix",
        black="#000000",
        red="#ff3333",
        green="#00ff41",
        yellow="#aaff00",
        blue="#00aaff",
        magenta="#cc33ff",
        cyan="#00ffff",
        white="#c0ffc0",
        bright_black="#1a1a1a",
        bright_red="#ff5555",
        bright_green="#33ff66",
        bright_yellow="#ccff33",
        bright_blue="#33bbff",
        bright_magenta="#dd66ff",
        bright_cyan="#66ffff",
        bright_white="#e0ffe0",
        background="#000000",
        foreground="#00ff41",
        cursor="#00ff41",
        font_family="monospace",
        font_size=11,
        bg_opacity=240,
    )


def build_dark_theme() -> TerminalTheme:
    """Default dark theme — calm, professional."""
    return TerminalTheme(
        name="Dark",
        black="#0c0c0c",
        red="#cd3131",
        green="#0dbc79",
        yellow="#e5e510",
        blue="#2472c8",
        magenta="#bc3fbc",
        cyan="#11a8cd",
        white="#cccccc",
        bright_black="#555555",
        bright_red="#f14c4c",
        bright_green="#23d18b",
        bright_yellow="#f5f543",
        bright_blue="#3b8eea",
        bright_magenta="#d670d6",
        bright_cyan="#29b8db",
        bright_white="#e5e5e5",
        background="#0c0c0c",
        foreground="#cccccc",
        cursor="#ffffff",
        font_family="monospace",
        font_size=10,
        bg_opacity=255,
    )


def build_light_theme() -> TerminalTheme:
    """Light theme — paper-like."""
    return TerminalTheme(
        name="Light",
        black="#000000",
        red="#cd0000",
        green="#00cd00",
        yellow="#cdcd00",
        blue="#0000ee",
        magenta="#cd00cd",
        cyan="#00cdcd",
        white="#e5e5e5",
        bright_black="#555555",
        bright_red="#ff0000",
        bright_green="#00ff00",
        bright_yellow="#ffff00",
        bright_blue="#5c5cff",
        bright_magenta="#ff00ff",
        bright_cyan="#00ffff",
        bright_white="#ffffff",
        background="#f0f0f0",
        foreground="#1a1a1a",
        cursor="#000000",
        font_family="monospace",
        font_size=10,
        bg_opacity=255,
    )


def build_amber_theme() -> TerminalTheme:
    """Retro amber CRT theme."""
    return TerminalTheme(
        name="Amber",
        black="#1a0a00",
        red="#ff5500",
        green="#ffaa00",
        yellow="#ffcc00",
        blue="#ff8800",
        magenta="#ff6600",
        cyan="#ff9900",
        white="#ffddaa",
        bright_black="#332200",
        bright_red="#ff7733",
        bright_green="#ffbb44",
        bright_yellow="#ffdd55",
        bright_blue="#ffaa44",
        bright_magenta="#ff8855",
        bright_cyan="#ffbb66",
        bright_white="#ffeecc",
        background="#1a0a00",
        foreground="#ffb000",
        cursor="#ffb000",
        font_family="monospace",
        font_size=11,
        bg_opacity=240,
    )


BUILTIN_THEMES: dict[str, TerminalTheme] = {
    "Dark": build_dark_theme(),
    "Matrix": build_matrix_theme(),
    "Amber": build_amber_theme(),
    "Light": build_light_theme(),
}


def get_theme(name: str) -> TerminalTheme:
    """Get a theme by name (case-insensitive). Falls back to Dark."""
    return BUILTIN_THEMES.get(
        name,
        BUILTIN_THEMES.get(name.capitalize(), build_dark_theme()),
    )


def theme_names() -> list[str]:
    return list(BUILTIN_THEMES.keys())
