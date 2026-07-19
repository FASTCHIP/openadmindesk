"""Activity rail widget for left sidebar with mode switching."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
)
from PySide6.QtCore import Qt, Signal



class ActivityRail(QWidget):
    """Left sidebar activity rail with mode switching.
    
    Provides compact session tree, SFTP browser, tunnel manager, tools,
    macros, and vault access through mode buttons.
    """

    mode_changed = Signal(str)

    def __init__(self, include_planned_modes: bool = False) -> None:
        """Initialize the activity rail.

        By default only the Sessions mode is visible. Other workbench panels are
        kept available for tests/future wiring, but hidden from users until they
        are complete enough to be self-explanatory.
        """
        super().__init__()
        self.include_planned_modes = include_planned_modes
        
        # Store original constraints for reference
        self._original_min_width = 280
        self._original_max_width = 350
        
        # Initialize mode dictionaries
        self.mode_buttons = {}
        self.mode_widgets = {}
        
        # Create layout and store it as instance variable
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # Set size constraints using parent class methods to avoid recursion
        super().setMinimumWidth(280)
        super().setMaximumWidth(350)
        
        # Button bar
        button_bar = QWidget()
        button_bar_layout = QVBoxLayout(button_bar)
        button_bar_layout.setContentsMargins(8, 8, 8, 8)
        button_bar_layout.setSpacing(4)
        button_bar_layout.setAlignment(Qt.AlignTop)
        
        # Add mode buttons
        modes = [
            ("sessions", "Sessions", "Manage connection profiles"),
            ("tunnels", "Tunnels", "SSH port forwarding"),
        ]
        if include_planned_modes:
            modes.extend([
                ("sftp", "SFTP", "File transfer browser"),
                ("tools", "Tools", "Network utilities"),
                ("macros", "Macros", "Saved command sequences"),
                ("vault", "Vault", "Credential management"),
            ])
        
        for mode, icon_text, tooltip in modes:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 8px 12px;
                    text-align: left;
                    font-size: 13px;
                    border: none;
                    border-radius: 4px;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
                QPushButton:checked {
                    background-color: #007acc;
                    color: white;
                    font-weight: bold;
                }
            """)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            button_bar_layout.addWidget(btn)
            self.mode_buttons[mode] = btn
        
        self._layout.addWidget(button_bar)
        
        # Content area
        self.content_stack = QStackedWidget()
        self._layout.addWidget(self.content_stack)
        
        # Add mode content widgets
        for mode, _, _ in modes:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            self.mode_widgets[mode] = widget
            self.content_stack.addWidget(widget)
        
        # Set default mode
        self._set_mode("sessions")

    def setMinimumWidth(self, width: int) -> None:
        """Override to maintain minimum width constraint."""
        if width < self._original_min_width:
            super().setMinimumWidth(self._original_min_width)
        else:
            super().setMinimumWidth(width)
    
    def setMaximumWidth(self, width: int) -> None:
        """Override to maintain maximum width constraint."""
        if width > self._original_max_width:
            super().setMaximumWidth(self._original_max_width)
        else:
            super().setMaximumWidth(width)

    def _set_mode(self, mode: str) -> None:
        """Switch to the specified mode."""
        if mode not in self.mode_buttons or mode not in self.mode_widgets:
            return

        for btn in self.mode_buttons.values():
            btn.setChecked(False)

        self.mode_buttons[mode].setChecked(True)
        index = self.content_stack.indexOf(self.mode_widgets[mode])
        self.content_stack.setCurrentIndex(index)
        self.mode_changed.emit(mode)

    def set_sessions_widget(self, widget: QWidget) -> None:
        """Set the sessions widget for the sessions mode."""
        if "sessions" in self.mode_widgets:
            # Remove the placeholder widget
            placeholder = self.mode_widgets["sessions"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            # Add the real widget
            self.mode_widgets["sessions"] = widget
            self.content_stack.insertWidget(index, widget)
            
            # If sessions mode is currently active, update it
            if self.mode_buttons["sessions"].isChecked():
                self.content_stack.setCurrentWidget(widget)

    def set_sftp_widget(self, widget: QWidget) -> None:
        """Set the SFTP widget for the SFTP mode."""
        if "sftp" in self.mode_widgets:
            placeholder = self.mode_widgets["sftp"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            self.mode_widgets["sftp"] = widget
            self.content_stack.insertWidget(index, widget)

    def set_tunnels_widget(self, widget: QWidget) -> None:
        """Set the tunnels widget for the tunnels mode."""
        if "tunnels" in self.mode_widgets:
            placeholder = self.mode_widgets["tunnels"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            self.mode_widgets["tunnels"] = widget
            self.content_stack.insertWidget(index, widget)

    def set_tools_widget(self, widget: QWidget) -> None:
        """Set the tools widget for the tools mode."""
        if "tools" in self.mode_widgets:
            placeholder = self.mode_widgets["tools"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            self.mode_widgets["tools"] = widget
            self.content_stack.insertWidget(index, widget)

    def set_macros_widget(self, widget: QWidget) -> None:
        """Set the macros widget for the macros mode."""
        if "macros" in self.mode_widgets:
            placeholder = self.mode_widgets["macros"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            self.mode_widgets["macros"] = widget
            self.content_stack.insertWidget(index, widget)

    def set_vault_widget(self, widget: QWidget) -> None:
        """Set the vault widget for the vault mode."""
        if "vault" in self.mode_widgets:
            placeholder = self.mode_widgets["vault"]
            index = self.content_stack.indexOf(placeholder)
            self.content_stack.removeWidget(placeholder)
            
            self.mode_widgets["vault"] = widget
            self.content_stack.insertWidget(index, widget)