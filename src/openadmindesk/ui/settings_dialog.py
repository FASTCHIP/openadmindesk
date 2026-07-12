"""Central settings dialog — single place for global behaviour."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from typing import Optional

from openadmindesk.core.l10n import _
from openadmindesk.core.settings import AppSettings, SettingsStore


_TERMINAL_FONT_CHOICES = (
    "monospace",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
    "Ubuntu Mono",
    "Courier New",
)


class SettingsDialog(QDialog):
    """Tabbed settings dialog for application-wide preferences."""

    def __init__(
        self,
        store: SettingsStore,
        settings: AppSettings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._original = settings
        self._settings = settings  # will be modified in-place
        self.setWindowTitle(_("Settings"))
        self.setMinimumSize(520, 400)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), _("General"))
        tabs.addTab(self._terminal_tab(), _("Terminal"))
        tabs.addTab(self._sftp_tab(), _("SFTP"))
        tabs.addTab(self._logging_tab(), _("Logging"))
        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── tabs ─────────────────────────────────────────────────────────────────

    def _general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        from openadmindesk.core.l10n import available_languages
        self._lang_combo = QComboBox()
        langs = available_languages()
        for code, name in langs.items():
            self._lang_combo.addItem(f"{name} ({code})", code)
            if code == self._settings.language:
                self._lang_combo.setCurrentIndex(self._lang_combo.count() - 1)
        form.addRow(_("Language:"), self._lang_combo)

        return w

    def _terminal_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        s = self._settings

        # Font family
        self._term_font = QComboBox()
        self._term_font.setEditable(False)
        for family in _TERMINAL_FONT_CHOICES:
            self._term_font.addItem(family, family)
        idx = self._term_font.findData(s.terminal_font_family)
        if idx < 0:
            self._term_font.addItem(s.terminal_font_family, s.terminal_font_family)
            idx = self._term_font.count() - 1
        self._term_font.setCurrentIndex(idx)
        form.addRow(_("Font family:"), self._term_font)

        # Font size
        self._term_font_size = QSpinBox()
        self._term_font_size.setRange(
            s.terminal_font_size_min, s.terminal_font_size_max
        )
        self._term_font_size.setValue(s.terminal_font_size)
        form.addRow(_("Font size:"), self._term_font_size)

        # Background opacity
        self._term_opacity = QSpinBox()
        self._term_opacity.setRange(
            s.terminal_opacity_min, s.terminal_opacity_max
        )
        self._term_opacity.setValue(s.terminal_bg_opacity)
        self._term_opacity.setSuffix(" / 255")
        form.addRow(_("BG opacity:"), self._term_opacity)

        # Cursor blink
        self._cursor_blink = QSpinBox()
        self._cursor_blink.setRange(100, 5000)
        self._cursor_blink.setValue(s.terminal_cursor_blink_ms)
        self._cursor_blink.setSuffix(" ms")
        form.addRow(_("Cursor blink:"), self._cursor_blink)

        # Scrollback
        self._scrollback = QSpinBox()
        self._scrollback.setRange(100, 100000)
        self._scrollback.setValue(s.terminal_scrollback_lines)
        form.addRow(_("Scrollback lines:"), self._scrollback)

        # Default columns
        self._term_cols = QSpinBox()
        self._term_cols.setRange(40, 400)
        self._term_cols.setValue(s.terminal_default_columns)
        form.addRow(_("Default columns:"), self._term_cols)

        # Default rows
        self._term_rows = QSpinBox()
        self._term_rows.setRange(10, 200)
        self._term_rows.setValue(s.terminal_default_rows)
        form.addRow(_("Default rows:"), self._term_rows)

        # Paste warning
        self._paste_warning = QCheckBox()
        self._paste_warning.setChecked(s.terminal_paste_warning)
        form.addRow(_("Warn on paste:"), self._paste_warning)

        return w

    def _sftp_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        s = self._settings

        # Show hidden files
        self._sftp_hidden = QCheckBox()
        self._sftp_hidden.setChecked(s.sftp_show_hidden_files)
        form.addRow(_("Show hidden files:"), self._sftp_hidden)

        # Tree font size
        self._sftp_font_size = QSpinBox()
        self._sftp_font_size.setRange(8, 24)
        self._sftp_font_size.setValue(s.sftp_tree_font_size)
        form.addRow(_("Tree font size:"), self._sftp_font_size)

        # Double-click action
        self._sftp_double_click = QComboBox()
        self._sftp_double_click.addItem(_("Edit file"), "edit")
        self._sftp_double_click.addItem(_("Download file"), "download")
        self._sftp_double_click.addItem(_("Open in system"), "open")
        idx = self._sftp_double_click.findData(s.sftp_double_click_action)
        if idx >= 0:
            self._sftp_double_click.setCurrentIndex(idx)
        form.addRow(_("Double-click action:"), self._sftp_double_click)

        # Default remote path
        self._sftp_default_path = QLineEdit(s.sftp_default_path)
        form.addRow(_("Default path:"), self._sftp_default_path)

        return w

    def _logging_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._log_level = QComboBox()
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in levels:
            self._log_level.addItem(level, level)
        idx = self._log_level.findData(self._settings.log_level)
        if idx >= 0:
            self._log_level.setCurrentIndex(idx)
        form.addRow(_("Log level:"), self._log_level)

        return w

    # ── accept ───────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        """Apply changes to the settings object and save."""
        s = self._settings

        # General
        s.language = self._lang_combo.currentData() or "en"

        # Terminal
        s.terminal_font_family = self._term_font.currentData() or "monospace"
        s.terminal_font_size = self._term_font_size.value()
        s.terminal_bg_opacity = self._term_opacity.value()
        s.terminal_cursor_blink_ms = self._cursor_blink.value()
        s.terminal_scrollback_lines = self._scrollback.value()
        s.terminal_default_columns = self._term_cols.value()
        s.terminal_default_rows = self._term_rows.value()
        s.terminal_paste_warning = self._paste_warning.isChecked()

        # SFTP
        s.sftp_show_hidden_files = self._sftp_hidden.isChecked()
        s.sftp_tree_font_size = self._sftp_font_size.value()
        s.sftp_double_click_action = self._sftp_double_click.currentData() or "edit"
        s.sftp_default_path = self._sftp_default_path.text().strip() or "/"

        # Logging
        s.log_level = self._log_level.currentData() or "INFO"

        self._store.save(s)
        self.accept()

    # ── result ────────────────────────────────────────────────────────────────

    def result_settings(self) -> AppSettings:
        """Return the (possibly modified) settings."""
        return self._settings
