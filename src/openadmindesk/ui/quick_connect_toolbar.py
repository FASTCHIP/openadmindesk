"""Quick connect toolbar."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QToolBar,
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal
from openadmindesk.core.l10n import _


class QuickConnectToolbar(QToolBar):
    """Quick connect toolbar for connecting to servers."""

    # Signal for when a connection is requested
    connect_requested = Signal(str)

    def __init__(self) -> None:
        """Initialize the quick connect toolbar."""
        super().__init__("Quick Connect")
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # Create widgets
        self._setup_toolbar()

    def _setup_toolbar(self) -> None:
        """Setup the toolbar widgets."""
        # Create layout for toolbar items
        toolbar_widget = QWidget()
        layout = QHBoxLayout(toolbar_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add connection input
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Enter host address")
        self.host_input.returnPressed.connect(self._on_connect)
        layout.addWidget(self.host_input)
        
        # Add connect button
        connect_button = QPushButton(_("Connect"))
        connect_button.clicked.connect(self._on_connect)
        layout.addWidget(connect_button)
        
        # Add toolbar widget
        self.addWidget(toolbar_widget)

    def _on_connect(self) -> None:
        """Handle connect button click."""
        host = self.host_input.text().strip()
        if host:
            self.connect_requested.emit(host)