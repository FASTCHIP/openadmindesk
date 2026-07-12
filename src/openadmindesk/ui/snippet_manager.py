"""Snippet manager UI — create, edit, and insert reusable command snippets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QToolBar,
    QToolButton,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QMessageBox,
    QMenu,
)
try:
    from PySide6.QtGui import QAction  # PySide6 >= 6.11
except ImportError:
    from PySide6.QtWidgets import QAction  # PySide6 < 6.11
from PySide6.QtCore import Qt, Signal
from typing import Optional

from openadmindesk.core.snippet_store import SnippetStore, Snippet
from openadmindesk.core.snippet_inserter import SnippetInserter

import time


class SnippetDialog(QDialog):
    """Dialog for adding/editing a snippet."""

    def __init__(self, snippet: Optional[Snippet] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.snippet = snippet
        self.setWindowTitle("Edit Snippet" if snippet else "New Snippet")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self._setup_ui()
        self._load_snippet()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("List directory contents")
        form.addRow("Name:", self.name_input)

        self.language_input = QComboBox()
        self.language_input.setEditable(True)
        self.language_input.addItems(["bash", "sh", "python", "sql", "docker",
                                      "git", "kubectl", "custom"])
        form.addRow("Language:", self.language_input)

        self.content_input = QPlainTextEdit()
        self.content_input.setPlaceholderText(
            "ls -la\n# or any multi-line command sequence"
        )
        self.content_input.setMinimumHeight(200)
        form.addRow("Content:", self.content_input)

        layout.addLayout(form)

        # Preview
        preview_label = QLabel("Preview (first 3 lines will be shown in list):")
        preview_label.setStyleSheet("color: gray;")
        layout.addWidget(preview_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_snippet(self) -> None:
        """Load snippet data into form."""
        if self.snippet:
            self.name_input.setText(self.snippet.name)
            idx = self.language_input.findText(self.snippet.language)
            if idx >= 0:
                self.language_input.setCurrentIndex(idx)
            self.content_input.setPlainText(self.snippet.content)

    def _validate_and_accept(self) -> None:
        """Validate and accept."""
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not self.content_input.toPlainText().strip():
            QMessageBox.warning(self, "Validation", "Content is required.")
            return
        self.accept()

    def get_snippet(self) -> Snippet:
        """Get snippet from form data."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        if self.snippet:
            s = self.snippet
            s.name = self.name_input.text().strip()
            s.language = self.language_input.currentText()
            s.content = self.content_input.toPlainText()
            s.updated_at = now
            return s
        else:
            return Snippet(
                id=f"snp_{int(time.time())}",
                name=self.name_input.text().strip(),
                content=self.content_input.toPlainText(),
                language=self.language_input.currentText(),
                created_at=now,
                updated_at=now
            )


class SnippetManagerWidget(QWidget):
    """Widget for managing and inserting snippets."""

    snippet_insert_requested = Signal(str, str)  # snippet_id, snippet_name

    def __init__(self, store: Optional[SnippetStore] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.store = store or SnippetStore()
        self.inserter = SnippetInserter(self.store)
        self._setup_ui()
        self._load_snippets()

    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        add_btn = QToolButton()
        add_btn.setText("+ New")
        add_btn.clicked.connect(self._add_snippet)
        toolbar.addWidget(add_btn)

        edit_btn = QToolButton()
        edit_btn.setText("✏ Edit")
        edit_btn.clicked.connect(self._edit_selected_snippet)
        toolbar.addWidget(edit_btn)

        delete_btn = QToolButton()
        delete_btn.setText("− Delete")
        delete_btn.clicked.connect(self._delete_selected_snippet)
        toolbar.addWidget(delete_btn)

        toolbar.addSeparator()

        insert_btn = QToolButton()
        insert_btn.setText("▶ Insert")
        insert_btn.setToolTip("Insert selected snippet into active terminal")
        insert_btn.clicked.connect(self._insert_selected_snippet)
        toolbar.addWidget(insert_btn)
        self._insert_btn = insert_btn

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search snippets...")
        self.search_input.textChanged.connect(self._filter_snippets)
        toolbar.addWidget(self.search_input)

        layout.addWidget(toolbar)

        # Info label
        self.info_label = QLabel(
            "Double-click a snippet to insert it into the active terminal."
        )
        self.info_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(self.info_label)

        # Snippet list
        self.snippet_tree = QTreeWidget()
        self.snippet_tree.setHeaderLabels(["Name", "Language", "Preview"])
        self.snippet_tree.setColumnWidth(0, 180)
        self.snippet_tree.setColumnWidth(1, 80)
        self.snippet_tree.setAlternatingRowColors(True)
        self.snippet_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.snippet_tree.itemDoubleClicked.connect(self._insert_selected_snippet)
        layout.addWidget(self.snippet_tree)

        self.setMinimumSize(450, 250)

    def _load_snippets(self, filter_text: str = "") -> None:
        """Load snippets into the tree, optionally filtered."""
        self.snippet_tree.clear()
        all_snippets = self.store.get_all_snippets()

        for s in all_snippets:
            if filter_text and filter_text.lower() not in s.name.lower():
                continue

            lines = s.content.split('\n')
            preview = lines[0] if lines else ""
            if len(preview) > 60:
                preview = preview[:57] + "..."

            item = QTreeWidgetItem([s.name, s.language, preview])
            item.setData(0, Qt.UserRole, s.id)
            item.setToolTip(0, s.name)
            item.setToolTip(2, s.content[:200] + ("..." if len(s.content) > 200 else ""))
            self.snippet_tree.addTopLevelItem(item)

    def _filter_snippets(self, text: str) -> None:
        """Filter snippet list."""
        self._load_snippets(text.strip())

    def _add_snippet(self) -> None:
        """Add a new snippet."""
        dialog = SnippetDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            snippet = dialog.get_snippet()
            if self.store.add_snippet(snippet):
                self._load_snippets(self.search_input.text().strip())

    def _edit_selected_snippet(self) -> None:
        """Edit the selected snippet."""
        item = self.snippet_tree.currentItem()
        if not item:
            return
        snippet_id = item.data(0, Qt.UserRole)
        snippet = self.store.get_snippet(snippet_id)
        if not snippet:
            return

        dialog = SnippetDialog(snippet, parent=self)
        if dialog.exec() == QDialog.Accepted:
            updated = dialog.get_snippet()
            if self.store.update_snippet(updated):
                self._load_snippets(self.search_input.text().strip())

    def _delete_selected_snippet(self) -> None:
        """Delete the selected snippet."""
        item = self.snippet_tree.currentItem()
        if not item:
            return

        reply = QMessageBox.question(
            self, "Delete Snippet",
            f"Delete snippet '{item.text(0)}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            snippet_id = item.data(0, Qt.UserRole)
            if self.store.delete_snippet(snippet_id):
                self._load_snippets(self.search_input.text().strip())

    def _insert_selected_snippet(self) -> None:
        """Request insertion of the selected snippet."""
        item = self.snippet_tree.currentItem()
        if not item:
            return

        snippet_id = item.data(0, Qt.UserRole)
        snippet_name = item.text(0)
        self.snippet_insert_requested.emit(snippet_id, snippet_name)

    def _show_context_menu(self, position) -> None:
        """Show context menu."""
        item = self.snippet_tree.itemAt(position)
        if not item:
            return

        menu = QMenu()

        insert_action = QAction("Insert into Terminal", self)
        insert_action.triggered.connect(self._insert_selected_snippet)
        menu.addAction(insert_action)

        menu.addSeparator()

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_selected_snippet)
        menu.addAction(edit_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_selected_snippet)
        menu.addAction(delete_action)

        menu.exec(self.snippet_tree.mapToGlobal(position))


class SnippetInsertButton(QToolButton):
    """Toolbar button that shows a dropdown of snippets to insert."""

    snippet_insert_requested = Signal(str, str)  # snippet_id, snippet_name

    def __init__(self, store: SnippetStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setText("📋 Snippets")
        self.setToolTip("Insert a command snippet")
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._build_menu()

    def _build_menu(self) -> None:
        """Build the dropdown menu from stored snippets."""
        menu = QMenu(self)

        snippets = self.store.get_all_snippets()
        if not snippets:
            noop = menu.addAction("(no snippets — add some first)")
            noop.setEnabled(False)
        else:
            for s in snippets:
                preview = s.content.split('\n')[0][:50]
                action = menu.addAction(f"{s.name}  —  {preview}")
                action.setData(s.id)
                action.triggered.connect(
                    lambda checked=False, sid=s.id, sname=s.name:
                        self.snippet_insert_requested.emit(sid, sname)
                )

        menu.addSeparator()
        manage_action = menu.addAction("Manage Snippets...")
        manage_action.triggered.connect(self._manage_requested)

        self.setMenu(menu)

    _manage_requested = Signal()

    def refresh(self) -> None:
        """Rebuild the menu (call after adding/deleting snippets)."""
        self._build_menu()
