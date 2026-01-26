import re
from typing import TYPE_CHECKING, List

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

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


class FileList(QListWidget):
    def __init__(self, parent, is_favorite: bool = False):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        self.main: MainWindow = parent
        self.is_favorite = is_favorite

        self.itemClicked.connect(self.main.file_single_clicked)
        self.doubleClicked.connect(self.main.file_double_clicked)
        self.setSortingEnabled(True)

        self.files_list: list[str] = []

        self.installEventFilter(self)

    def eventFilter(self, source: QObject, event: QEvent):
        if source is self and event.type() == QEvent.Type.KeyRelease:
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                current = self.currentItem()
                if current:
                    self.main.file_single_clicked()
        return super().eventFilter(source, event)

    def context_menu(self, pos):
        global_position = self.mapToGlobal(pos)

        menu = QMenu(self)
        menu.addAction("Delete selection", self.main.delete)
        menu.addAction("Extract selection", self.main.extract)
        menu.addAction("Rename file", self.main.rename)
        menu.addAction("Copy file name", self.main.copy_name)
        if self.is_favorite:
            menu.addAction("Remove from favorites", self.main.remove_favorites)
        else:
            menu.addAction("Add to favorites", self.main.add_favorites)

        menu.exec(global_position)

    def update_list(self):
        self.clear()
        if self.main.archive is None:
            return

        self.files_list = self.main.archive.file_list()
        self.addItems(self.files_list)

        self.main.filter_list()

    def add_files(self, files: List[str]):
        new_files = [file for file in files if file not in self.files_list]

        if new_files:
            self.addItems(new_files)
            self.files_list.extend(new_files)

    def remove_files(self, files: List[str]):
        files_set = set(files)
        i = 0
        while i < self.count():
            item_text = self.item(i).text()
            if item_text in files_set:
                self.takeItem(i)
                files_set.remove(item_text)
                self.files_list.remove(item_text)
                if not files_set:
                    break
            else:
                i += 1


class TabWidget(QTabWidget):
    def remove_tab(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()

        self.removeTab(index)


class FileListTabs(TabWidget):
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.favorite_list: FileList = None
        self.main = parent

    @property
    def active_list(self) -> FileList:
        return self.currentWidget()

    @property
    def all_lists(self) -> List[FileList]:
        return [
            self.widget(i) for i in range(self.count() - 1) if isinstance(self.widget(i), FileList)
        ]

    @property
    def all_but_favorite(self) -> List[FileList]:
        return [
            self.widget(i)
            for i in range(self.count() - 1)
            if isinstance(self.widget(i), FileList) and not self.widget(i).is_favorite
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
        self.favorite_list = FileList(self.main, is_favorite=True)
        self.insertTab(0, self.favorite_list, "Favorites")

    def add_favorites(self, files: List[str]):
        if self.favorite_list is None:
            self.create_favorite_tab()

        self.add_files_to_tab(self.favorite_list, files)

    def remove_favorites(self, files: List[str]):
        self.remove_files_from_tab(self.favorite_list, files)

    def add_files_to_tab(self, widget: FileList, files: List[str]):
        widget.add_files(files)

    def remove_files_from_tab(self, widget: FileList, files: List[str]):
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
