import os
import re
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING, List, TypeAlias

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from file_views import FileList, FileTree

if TYPE_CHECKING:
    from main import MainWindow


class SearchBox(QComboBox):
    def __init__(self, *args, enter_callback=None, placeholder_text="Search...", **kwargs):
        super().__init__(*args, **kwargs)
        self.enter_callback = enter_callback
        self.setEditable(True)

        if placeholder_text:
            self.lineEdit().setPlaceholderText(placeholder_text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.enter_callback:
                self.enter_callback()
            return

        super().keyPressEvent(event)


class ArchiveSearchThread(QThread):
    matched = pyqtSignal(tuple)

    def __init__(
        self,
        parent: "MainWindow",
        search: str,
        encoding: str,
        archive: base_archive.BaseArchive,
        regex: bool,
    ) -> None:
        super().__init__(parent)

        self.search = search
        self.encoding = encoding
        self.archive = archive
        self.regex = regex

    def run(self):
        matches = []
        buffer = self.archive.bytes().decode(self.encoding)
        indexes = {
            match.start()
            for match in re.finditer(self.search if self.regex else re.escape(self.search), buffer)
        }
        match_count = len(indexes)

        for name, entry in self.archive.entries.items():
            matched_indexes = {
                index
                for index in indexes
                if entry.position <= index < (entry.position + entry.size)
            }
            if matched_indexes:
                indexes -= matched_indexes
                matches.append(name)

            if not indexes:
                break

        for name, modified_entry in self.archive.modified_entries.items():
            has_match = re.findall(
                self.search if self.regex else re.escape(self.search), modified_entry.content
            )
            if has_match:
                matches.append(name)

        self.matched.emit((matches, match_count))


class TabWidget(QTabWidget):
    def remove_tab(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()

        self.removeTab(index)


FileListObject: TypeAlias = FileList | FileTree


class FileListTabs(TabWidget):
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.favorite_list: FileListObject = None
        self.main = parent

    @property
    def active_list(self) -> FileListObject:
        return self.currentWidget()

    @property
    def all_lists(self) -> List[FileListObject]:
        return [
            self.widget(i)
            for i in range(self.count() - 1)
            if isinstance(self.widget(i), (FileList, FileTree))
        ]

    @property
    def all_but_favorite(self) -> List[FileListObject]:
        return [
            self.widget(i)
            for i in range(self.count() - 1)
            if isinstance(self.widget(i), (FileList, FileTree)) and not self.widget(i).is_favorite
        ]

    def update_list(self, all=False):
        to_update = self.all_but_favorite if all else [self.active_list]
        for widget in to_update:
            widget.update_list()

    def add_files(self, files: List[str]):
        for widget in self.all_but_favorite:
            self.add_files_to_tab(widget, files)

    def remove_files(self, files: List[str]):
        for widget in self.all_lists:
            self.remove_files_from_tab(widget, files)

    def create_favorite_tab(self):
        self.favorite_list = FileTree(self.main, is_favorite=True)
        self.insertTab(0, self.favorite_list, "Favorites")

    def add_favorites(self, files: List[str]):
        if self.favorite_list is None:
            self.create_favorite_tab()

        self.add_files_to_tab(self.favorite_list, files)

    def remove_favorites(self, files: List[str]):
        self.remove_files_from_tab(self.favorite_list, files)

    def add_files_to_tab(self, widget: FileListObject, files: List[str]):
        widget.add_files(files)

    def remove_files_from_tab(self, widget: FileListObject, files: List[str]):
        widget.remove_files(files)


class WrappingInputDialog(QDialog):
    def __init__(self, title="Input", label="Enter text:", parent=None, fixed_width: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(fixed_width)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))

        self.textEdit = QTextEdit()
        self.textEdit.setAcceptRichText(False)

        self.textEdit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.textEdit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        self.textEdit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.textEdit.installEventFilter(self)
        layout.addWidget(self.textEdit)

        self.textEdit.textChanged.connect(self.adjustHeightToContent)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.adjustHeightToContent()

    def adjustHeightToContent(self):
        viewport_width = self.textEdit.viewport().width()
        self.textEdit.document().setTextWidth(viewport_width)

        doc_height = self.textEdit.document().size().height()
        margins = self.textEdit.contentsMargins().top() + self.textEdit.contentsMargins().bottom()
        doc_margin = self.textEdit.document().documentMargin()

        line_height = self.textEdit.fontMetrics().lineSpacing()
        target_height = int(max(line_height * 1.6, doc_height + margins + doc_margin + 12))

        max_height = 300
        target_height = min(target_height, max_height)

        self.textEdit.setFixedHeight(target_height)

        self.adjustSize()

    def eventFilter(self, obj, event):
        if obj == self.textEdit and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept()
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def getText(
        parent=None, title="Input", label="Enter text:", default="", fixed_width: int = 500
    ):
        dialog = WrappingInputDialog(title, label, parent, fixed_width=fixed_width)
        dialog.textEdit.setPlainText(default)
        dialog.adjustHeightToContent()
        result = dialog.exec()
        text = dialog.textEdit.toPlainText().strip()
        ok = result == QDialog.DialogCode.Accepted
        return text, ok


class NewTabDialog(QDialog):
    def __init__(self, parent: "MainWindow" = None, default_name="List"):
        super().__init__(parent)
        self.setWindowTitle("New File Tab")
        self.setFixedWidth(400)
        self.parent_window = parent

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Tab name:"))
        self.name_input = QLineEdit()
        self.name_input.setText(default_name)
        self.name_input.selectAll()
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("\nView type:"))

        default_type = parent.settings.default_file_list_type
        self.button_group = QButtonGroup(self)

        self.tree_radio = QRadioButton("Folder View")
        self.tree_radio.setChecked(default_type == "tree")
        self.button_group.addButton(self.tree_radio)
        layout.addWidget(self.tree_radio)

        self.list_radio = QRadioButton("List View")
        self.list_radio.setChecked(default_type == "list")
        self.button_group.addButton(self.list_radio)
        layout.addWidget(self.list_radio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_input.setFocus()

    def validate_and_accept(self):
        """Validate the tab name before accepting the dialog"""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(
                self, "Invalid Name", "Tab name cannot be blank. Please enter a valid name."
            )
            self.name_input.setFocus()
            return

        existing_names = {
            self.parent_window.listwidget.tabText(i)
            for i in range(self.parent_window.listwidget.count() - 1)
        }

        if name in existing_names:
            QMessageBox.warning(
                self,
                "Duplicate Name",
                f"A tab named '{name}' already exists. Please choose a different name.",
            )
            self.name_input.selectAll()
            self.name_input.setFocus()
            return

        self.accept()

    def get_values(self):
        """Returns (name, widget_type) where widget_type is 'tree' or 'list'"""
        name = self.name_input.text().strip()
        widget_type = "tree" if self.tree_radio.isChecked() else "list"
        return name, widget_type


class WorkspaceDialog(QDialog):
    def __init__(self, parent: "MainWindow" = None, workspaces: List[str] = []):
        super().__init__(parent)
        self.main = parent
        self.workspaces = workspaces
        self.selected_workspace = None

        self.setWindowTitle("Workspace Management")
        self.setMinimumSize(700, 500)

        self.setup_ui()
        self.load_workspaces()

    def setup_ui(self):
        """Setup the dialog UI with list and info panel."""
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QDialog()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Workspaces:"))
        self.workspace_list = QListWidget()
        self.workspace_list.itemSelectionChanged.connect(self.on_workspace_selected)
        self.workspace_list.itemDoubleClicked.connect(self.open_selected_workspace)
        left_layout.addWidget(self.workspace_list)

        splitter.addWidget(left_widget)

        right_widget = QDialog()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("Workspace Information:"))

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold;")
        name_layout.addWidget(self.name_label)
        name_layout.addStretch()
        right_layout.addLayout(name_layout)

        right_layout.addWidget(QLabel("Archive:"))
        self.archive_label = QLabel()
        self.archive_label.setWordWrap(True)
        self.archive_label.setStyleSheet("margin-left: 10px; color: #666;")
        right_layout.addWidget(self.archive_label)

        modified_layout = QHBoxLayout()
        modified_layout.addWidget(QLabel("Last Modified:"))
        self.modified_label = QLabel()
        self.modified_label.setStyleSheet("color: #666;")
        modified_layout.addWidget(self.modified_label)
        modified_layout.addStretch()
        right_layout.addLayout(modified_layout)

        right_layout.addWidget(QLabel("\nNotes:"))
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Add notes about this workspace...")
        self.notes_edit.textChanged.connect(self.on_notes_changed)
        right_layout.addWidget(self.notes_edit)

        splitter.addWidget(right_widget)
        splitter.setSizes([250, 450])

        layout.addWidget(splitter)

        button_layout = QHBoxLayout()

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_selected_workspace)
        self.open_button.setEnabled(False)
        button_layout.addWidget(self.open_button)

        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_workspace)
        self.rename_button.setEnabled(False)
        button_layout.addWidget(self.rename_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_workspace)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch()

        self.folder_button = QPushButton("Open Folder")
        self.folder_button.clicked.connect(self.open_workspace_folder)
        button_layout.addWidget(self.folder_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def load_workspaces(self):
        """Load workspaces into the list."""
        self.workspace_list.clear()
        for workspace in self.workspaces:
            self.workspace_list.addItem(workspace)

        if self.workspaces:
            self.workspace_list.setCurrentRow(0)

    def on_workspace_selected(self):
        """Handle workspace selection."""
        selected_items = self.workspace_list.selectedItems()
        if not selected_items:
            self.clear_info_panel()
            return

        workspace_name = selected_items[0].text()
        self.selected_workspace = workspace_name
        self.load_workspace_info(workspace_name)

        self.open_button.setEnabled(True)
        self.rename_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def load_workspace_info(self, workspace_name: str):
        """Load and display workspace information."""
        data = self.main.settings.get_workspace(workspace_name)

        self.name_label.setText(workspace_name)
        self.archive_label.setText(data.get("archive_path", "N/A"))

        workspace_path = self.main.settings.get_workspace_path(workspace_name)
        if os.path.exists(workspace_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(workspace_path))
            self.modified_label.setText(mod_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.modified_label.setText("N/A")

        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(data.get("notes", ""))
        self.notes_edit.blockSignals(False)

    def clear_info_panel(self):
        """Clear the info panel."""
        self.name_label.setText("")
        self.archive_label.setText("")
        self.modified_label.setText("")
        self.notes_edit.clear()
        self.selected_workspace = None

        self.open_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def on_notes_changed(self):
        """Save notes when changed."""
        if not self.selected_workspace:
            return

        data = self.main.settings.get_workspace(self.selected_workspace)
        data["notes"] = self.notes_edit.toPlainText()
        self.main.settings.save_workspace(self.selected_workspace, data)

    def open_selected_workspace(self):
        """Open the selected workspace."""
        if not self.selected_workspace:
            return
        self.accept()

    def rename_workspace(self):
        """Rename the selected workspace."""
        if not self.selected_workspace:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Workspace", "Enter new name:", text=self.selected_workspace
        )

        if not ok or not new_name:
            return

        if new_name == self.selected_workspace:
            return

        if self.main.settings.workspace_exists(new_name):
            QMessageBox.warning(
                self, "Name Exists", f"A workspace named '{new_name}' already exists."
            )
            return

        if self.main.settings.rename_workspace(self.selected_workspace, new_name):
            old_name = self.selected_workspace
            self.workspaces[self.workspaces.index(old_name)] = new_name
            self.selected_workspace = new_name

            current_row = self.workspace_list.currentRow()
            self.load_workspaces()
            self.workspace_list.setCurrentRow(current_row)

            QMessageBox.information(self, "Renamed", f"Workspace renamed to '{new_name}'")
        else:
            QMessageBox.warning(self, "Error", "Failed to rename workspace.")

    def delete_workspace(self):
        """Delete the selected workspace."""
        if not self.selected_workspace:
            return

        ret = QMessageBox.question(
            self,
            "Delete Workspace?",
            f"Are you sure you want to delete the workspace <b>{self.selected_workspace}</b>?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if ret == QMessageBox.StandardButton.Yes:
            self.main.settings.delete_workspace(self.selected_workspace)
            self.workspaces.remove(self.selected_workspace)

            if not self.workspaces:
                QMessageBox.information(self, "No Workspaces", "No more workspaces available.")
                self.reject()
                return

            self.load_workspaces()

    def open_workspace_folder(self):
        """Open the workspace folder in the file explorer."""
        workspace_folder = self.main.settings.workspace_folder
        if os.path.exists(workspace_folder):
            webbrowser.open(workspace_folder)
        else:
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The workspace folder does not exist:\n{workspace_folder}",
            )

    def textValue(self) -> str:
        """Return the selected workspace name."""
        return self.selected_workspace
