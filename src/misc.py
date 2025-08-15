import re
from typing import TYPE_CHECKING, List

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QMenu,
    QTabWidget,
)
from pyBIG import base_archive


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
        self.archive.repack()

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
                if entry.position <= index <= (entry.position + entry.size)
            }
            if matched_indexes:
                indexes -= matched_indexes
                matches.append(name)
                continue

        self.matched.emit((matches, match_count))


class FileList(QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        self.main: MainWindow = parent

    def context_menu(self, pos):
        global_position = self.mapToGlobal(pos)

        menu = QMenu(self)
        menu.addAction("Delete selection", self.main.delete)
        menu.addAction("Extract selection", self.main.extract)
        menu.addAction("Rename file", self.main.rename)
        menu.addAction("Copy file name", self.main.copy_name)

        menu.exec(global_position)

    def update_list(self):
        self.clear()
        if self.main.archive is None:
            return

        self.addItems(self.main.archive.file_list())

        self.main.filter_list()


class TabWidget(QTabWidget):
    def remove_tab(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()

        self.removeTab(index)


class FileListTabs(TabWidget):
    @property
    def active_list(self) -> FileList:
        return self.currentWidget()

    @property
    def all_lists(self) -> List[FileList]:
        return [
            self.widget(i) for i in range(self.count() - 1) if isinstance(self.widget(i), FileList)
        ]

    @property
    def all_but_active(self) -> List[FileList]:
        return [
            self.widget(i)
            for i in range(self.count() - 1)
            if i != self.currentIndex() and isinstance(self.widget(i), FileList)
        ]

    def update_list(self, all=False):
        to_update = self.all_lists if all else [self.active_list]
        for widget in to_update:
            widget.update_list()

    def add_files(self, files: List[str]):
        for widget in self.all_lists:
            items = [widget.item(x).text() for x in range(widget.count())]
            new_files = [file for file in files if file not in items]

            if new_files:
                widget.insertItems(widget.count(), new_files)
                widget.sortItems()

    def remove_files(self, files: List[str]):
        for widget in self.all_lists:
            file_list = files.copy()
            for i in reversed(range(widget.count())):
                file = widget.item(i).text()
                if file in file_list:
                    widget.takeItem(i)
                    file_list.remove(file)

                if not file_list:
                    break
