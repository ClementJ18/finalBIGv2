import os
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from main import MainWindow


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
        workplace = self.main.settings.get_workspace(workspace_name)

        self.name_label.setText(workspace_name)
        self.archive_label.setText(workplace.archive_path or "N/A")

        workspace_path = self.main.settings.get_workspace_path(workspace_name)
        if os.path.exists(workspace_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(workspace_path))
            self.modified_label.setText(mod_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.modified_label.setText("N/A")

        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(workplace.notes or "")
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

        workplace = self.main.settings.get_workspace(self.selected_workspace)
        workplace.notes = self.notes_edit.toPlainText()
        self.main.settings.save_workspace(self.selected_workspace, workplace)

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
