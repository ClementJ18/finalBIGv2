import os
import re
from typing import TYPE_CHECKING, List

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QListWidget,
    QMenu,
    QMessageBox,
    QTabWidget,
)
from pyBIG import base_archive

from utils import normalize_name

if TYPE_CHECKING:
    from main import MainWindow


class ArchiveSearchThread(QThread):
    matched = pyqtSignal(tuple)

    def __init__(self, parent, search, encoding, archive: base_archive.BaseArchive, regex) -> None:
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

    def _add_file(self, url, name, blank=False, skip_all=False):
        ret = None
        if self.main.archive.file_exists(name):
            if not skip_all:
                ret = QMessageBox.question(
                    self,
                    "Overwrite file?",
                    f"<b>{name}</b> already exists, overwrite?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.YesToAll,
                    QMessageBox.StandardButton.No,
                )
                if ret == QMessageBox.StandardButton.No:
                    return ret

            self.main.archive.remove_file(name)

        try:
            if blank:
                self.main.archive.add_file(name, b"")
            else:
                with open(url, "rb") as f:
                    self.main.archive.add_file(name, f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return ret

        return ret

    def add_file(self, url, *, blank=False, ask_name=True):
        name = normalize_name(url)
        if ask_name:
            name, ok = QInputDialog.getText(
                self,
                "Filename",
                "Save the file under the following name:",
                text=name,
            )
            if not ok or not name:
                return False

        ret = self._add_file(url, name, blank)
        if ret != QMessageBox.StandardButton.No:
            self.main.listwidget.add_files([name], ret is not None)

    def add_folder(self, url):
        skip_all = False
        common_dir = os.path.dirname(url)
        files_to_add = []
        for root, _, files in os.walk(url):
            for f in files:
                full_path = os.path.join(root, f)
                name = normalize_name(os.path.relpath(full_path, common_dir))
                ret = self._add_file(full_path, name, blank=False, skip_all=skip_all)

                if ret != QMessageBox.StandardButton.No:
                    files_to_add.append(name)

                if ret == QMessageBox.StandardButton.YesToAll:
                    skip_all = True

        self.main.listwidget.add_files(files_to_add)

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
            self.widget(i) for i in range(self.count() - 1) if isinstance(self.widget(1), FileList)
        ]

    @property
    def all_but_active(self) -> List[FileList]:
        return [
            self.widget(i)
            for i in range(self.count() - 1)
            if i != self.currentIndex() and isinstance(self.widget(1), FileList)
        ]

    def update_list(self, all=False):
        to_update = self.all_lists if all else [self.active_list]
        for widget in to_update:
            widget.update_list()

    def add_files(self, files, replace=False):
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
