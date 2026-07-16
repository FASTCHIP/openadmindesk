#!/usr/bin/env python3
"""Demonstration of the new split workspace functionality."""

from PySide6.QtWidgets import QApplication, QMessageBox
from openadmindesk.ui.main_window import MainWindow


def main():
    """Demonstrate the split workspace functionality."""
    app = QApplication(["demo"])

    # Create main window
    window = MainWindow()
    window.show()

    # Show demonstration message
    msg = QMessageBox()
    msg.setWindowTitle("Split Workspace Demo")
    msg.setText("""
    🎉 Split Workspace Panes Feature Demo

    This demonstrates the new true split workspace functionality:

    📋 Available Layouts:
    - Single (1): One workspace (default)
    - Horizontal (2): Two side-by-side workspaces
    - Vertical (2): Two stacked workspaces
    - Grid (4): Four workspaces in a 2x2 grid

    🎯 How to use:
    1. Use the "View" toolbar buttons to switch layouts
    2. New sessions always open in the active (focused) workspace
    3. Each workspace has its own set of tabs
    4. Broadcast mode works across all workspaces

    🔧 Technical Details:
    - WorkspaceContainer manages multiple TabbedWorkspace instances
    - Active workspace detection based on focus
    - Session routing to the focused workspace
    - Status bar aggregates counts from all workspaces

    Try it out! Click the layout buttons in the View toolbar.
    """)
    msg.setIcon(QMessageBox.Information)
    msg.exec()

    return app.exec()


if __name__ == "__main__":
    main()
