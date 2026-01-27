import re
from typing import TYPE_CHECKING, List, TypeAlias

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
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

        from PyQt6.QtWidgets import QButtonGroup, QLineEdit, QRadioButton

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


class WorkspaceDialog(QInputDialog):
    def __init__(self, parent: "MainWindow" = None, workspaces: List[str] = []):
        super().__init__(parent)
        self.setWindowTitle("Workspace Management")
        self.setLabelText("Select a workspace to open:")
        self.setComboBoxItems(workspaces)
        self.setOption(QInputDialog.InputDialogOption.UseListViewForComboBoxItems)

        delete_button = QPushButton("Delete Workspace")
        delete_button.clicked.connect(lambda: parent.delete_workspace(self))
        button_box: QDialogButtonBox = self.findChild(QDialogButtonBox)
        button_box.addButton(delete_button, QDialogButtonBox.ButtonRole.ActionRole)

        self.workspaces = workspaces
