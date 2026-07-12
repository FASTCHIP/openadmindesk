"""Terminal settings dialog — theme, font, opacity."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QSlider,
    QGroupBox,
    QLabel,
    QFontComboBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from openadmindesk.ui.terminal_theme import (
    TerminalTheme, BUILTIN_THEMES, theme_names,
)
from openadmindesk.core.l10n import _


class TerminalSettingsDialog(QDialog):
    """Dialog for configuring terminal appearance."""

    def __init__(self, current_theme: TerminalTheme, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Terminal Settings"))
        self.setMinimumWidth(420)
        self._result_theme = current_theme
        self._setup_ui(current_theme)

    def _setup_ui(self, theme: TerminalTheme) -> None:
        layout = QVBoxLayout(self)

        # ── Theme preset ──────────────────────────────────────────────────
        preset_group = QGroupBox(_("Theme Preset"))
        preset_layout = QFormLayout(preset_group)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(theme_names())
        # Select current theme
        for i, name in enumerate(theme_names()):
            if name.lower() == theme.name.lower():
                self.preset_combo.setCurrentIndex(i)
                break
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addRow(_("Preset:"), self.preset_combo)

        layout.addWidget(preset_group)

        # ── Font ──────────────────────────────────────────────────────────
        font_group = QGroupBox(_("Font"))
        font_layout = QFormLayout(font_group)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(theme.font_family))
        font_layout.addRow(_("Family:"), self.font_combo)

        self.font_size = QSpinBox()
        self.font_size.setRange(6, 32)
        self.font_size.setValue(theme.font_size)
        font_layout.addRow(_("Size:"), self.font_size)

        layout.addWidget(font_group)

        # ── Opacity ───────────────────────────────────────────────────────
        opacity_group = QGroupBox(_("Background Opacity"))
        opacity_layout = QVBoxLayout(opacity_group)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 255)
        self.opacity_slider.setValue(theme.bg_opacity)
        self.opacity_slider.setTickPosition(QSlider.TicksBelow)
        self.opacity_slider.setTickInterval(25)

        self.opacity_label = QLabel(
            f"{theme.bg_opacity}/255  ({theme.bg_opacity * 100 // 255}%)"
        )
        self.opacity_label.setAlignment(Qt.AlignCenter)
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(
                f"{v}/255  ({v * 100 // 255}%)"
            )
        )

        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        layout.addWidget(opacity_group)

        # ── Buttons ───────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_preset_changed(self, name: str) -> None:
        preset = BUILTIN_THEMES.get(name)
        if preset:
            self.font_combo.setCurrentFont(QFont(preset.font_family))
            self.font_size.setValue(preset.font_size)
            self.opacity_slider.setValue(preset.bg_opacity)

    def _on_accept(self) -> None:
        theme_name = self.preset_combo.currentText()
        preset = BUILTIN_THEMES.get(theme_name)
        if preset:
            self._result_theme = TerminalTheme(
                name=preset.name,
                black=preset.black,
                red=preset.red,
                green=preset.green,
                yellow=preset.yellow,
                blue=preset.blue,
                magenta=preset.magenta,
                cyan=preset.cyan,
                white=preset.white,
                bright_black=preset.bright_black,
                bright_red=preset.bright_red,
                bright_green=preset.bright_green,
                bright_yellow=preset.bright_yellow,
                bright_blue=preset.bright_blue,
                bright_magenta=preset.bright_magenta,
                bright_cyan=preset.bright_cyan,
                bright_white=preset.bright_white,
                background=preset.background,
                foreground=preset.foreground,
                cursor=preset.cursor,
                font_family=self.font_combo.currentFont().family(),
                font_size=self.font_size.value(),
                bg_opacity=self.opacity_slider.value(),
            )
        self.accept()

    def result_theme(self) -> TerminalTheme:
        return self._result_theme
