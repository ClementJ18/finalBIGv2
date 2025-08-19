import re
from typing import TYPE_CHECKING, List

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QMenu,
    QTabWidget,
)

if TYPE_CHECKING:
    from main import MainWindow


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
        if source is self and event.type() == QEvent.Type.KeyPress:
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
        self.setCurrentIndex(0)

    def remove_favorites(self, files: List[str]):
        self.remove_files_from_tab(self.favorite_list, files)

    def add_files_to_tab(self, widget: FileList, files: List[str]):
        widget.add_files(files)

    def remove_files_from_tab(self, widget: FileList, files: List[str]):
        widget.remove_files(files)
