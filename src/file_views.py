from typing import TYPE_CHECKING, List

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

if TYPE_CHECKING:
    from main import MainWindow


class FileViewAbstract:
    def context_menu(self, pos):
        raise NotImplementedError

    def update_list(self):
        raise NotImplementedError

    def add_files(self, files: List[str]):
        raise NotImplementedError

    def remove_files(self, files: List[str]):
        raise NotImplementedError

    def is_file_selected(self) -> bool:
        raise NotImplementedError

    def get_selected_files(self) -> List[str]:
        raise NotImplementedError

    def get_items(self) -> List[QObject]:
        raise NotImplementedError

    def current_item_text(self) -> str:
        raise NotImplementedError

    def is_valid_selection(self) -> bool:
        raise NotImplementedError

    def post_filter(self):
        raise NotImplementedError


class FileList(QListWidget):
    def __init__(self, parent, is_favorite: bool = False):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        self.main: "MainWindow" = parent
        self.is_favorite = is_favorite

        self.itemClicked.connect(self.main.file_single_clicked)
        self.doubleClicked.connect(self.main.file_double_clicked)
        self.setSortingEnabled(True)

        self.files_list: list[str] = []
        self.filter = None

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

        self.main.filter_list_from_search()

    def add_files(self, files: List[str]):
        new_files = [file for file in files if file not in self.files_list]

        if new_files:
            self.addItems(new_files)
            self.files_list.extend(new_files)

    def remove_files(self, files: List[str]):
        files_set = set(files)
        i = 0
        while i < self.count():
            item_text = self.get_item_path(self.item(i))
            if item_text in files_set:
                self.takeItem(i)
                files_set.remove(item_text)
                self.files_list.remove(item_text)
                if not files_set:
                    break
            else:
                i += 1

    def is_file_selected(self) -> bool:
        if not self.selectedItems():
            return False

        return True

    def get_selected_files(self) -> List[str]:
        return [self.get_item_path(item) for item in self.selectedItems()]

    def get_items(self) -> List[QListWidgetItem]:
        return [self.item(i) for i in range(self.count())]

    def current_item_text(self) -> str:
        current_item = self.currentItem()
        if current_item:
            return self.get_item_path(current_item)
        return ""

    def is_valid_selection(self):
        return True

    def post_filter(self):
        pass

    def get_item_path(self, item: QListWidgetItem) -> str:
        return item.text()


class FileTree(QTreeWidget):
    def __init__(self, parent, is_favorite: bool = False):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        self.main: "MainWindow" = parent
        self.is_favorite = is_favorite

        self.itemClicked.connect(self.main.file_single_clicked)
        self.doubleClicked.connect(self.main.file_double_clicked)
        self.setSortingEnabled(False)

        self.files_list: list[str] = []
        self.filter = None

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

        self.files_list = []
        file_list = self.main.archive.file_list()
        self.add_files(file_list)
        self._sort_items_recursively()

        self.main.filter_list_from_search()

    def add_files(self, files: List[str]):
        """Add files with directory structure"""
        for filepath in files:
            if filepath in self.files_list:
                continue

            parts = filepath.replace("\\", "/").split("/")
            parent_item = self.invisibleRootItem()

            for i, part in enumerate(parts[:-1]):
                folder_item = self._find_or_create_folder(parent_item, part)
                parent_item = folder_item

            file_item = QTreeWidgetItem(parent_item, [parts[-1]])
            file_item.setData(0, Qt.ItemDataRole.UserRole, filepath)
            self.files_list.append(filepath)

    def _find_or_create_folder(self, parent: QTreeWidgetItem, folder_name: str):
        """Find existing folder or create new one"""
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) == folder_name and child.childCount() >= 0:
                return child

        folder_item = QTreeWidgetItem(parent, [folder_name])
        folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
        folder_item.setData(0, Qt.ItemDataRole.UserRole + 1, f"0_{folder_name}")
        return folder_item

    def _sort_items_recursively(self, parent: QTreeWidgetItem = None):
        """Sort items with folders first, then files, both alphabetically"""
        if parent is None:
            parent = self.invisibleRootItem()

        for i in range(parent.childCount()):
            self._sort_items_recursively(parent.child(i))

        items = []
        for i in range(parent.childCount()):
            items.append(parent.takeChild(0))

        items.sort(
            key=lambda item: (
                0 if item.data(0, Qt.ItemDataRole.UserRole) is None else 1,
                item.text(0).lower(),
            )
        )

        for item in items:
            parent.addChild(item)

    def remove_files(self, files: List[str]):
        """Remove files by their full paths from the tree structure"""
        files_set = set(files)

        def remove_from_tree(parent: QTreeWidgetItem):
            i = 0
            while i < parent.childCount():
                child = parent.child(i)
                filepath = child.data(0, Qt.ItemDataRole.UserRole)

                if filepath is not None and filepath in files_set:
                    parent.takeChild(i)
                    files_set.remove(filepath)
                    self.files_list.remove(filepath)
                    if not files_set:
                        return True
                else:
                    if remove_from_tree(child):
                        return True
                    i += 1
            return False

        remove_from_tree(self.invisibleRootItem())
        self._remove_empty_folders()

    def _remove_empty_folders(self):
        """Remove folders that have no children"""

        def cleanup(parent: QTreeWidgetItem):
            i = 0
            while i < parent.childCount():
                child = parent.child(i)
                cleanup(child)

                if child.data(0, Qt.ItemDataRole.UserRole) is None and child.childCount() == 0:
                    parent.takeChild(i)
                else:
                    i += 1

        cleanup(self.invisibleRootItem())

    def get_selected_files(self) -> List[str]:
        selected_files = []
        for item in self.selectedItems():
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if file_path is not None:
                selected_files.append(file_path)
        return selected_files

    def is_file_selected(self) -> bool:
        selected_files = [
            item
            for item in self.selectedItems()
            if item.data(0, Qt.ItemDataRole.UserRole) is not None
        ]

        if not selected_files:
            return False

        return True

    def get_items(self) -> List[QTreeWidgetItem]:
        items = []

        def traverse(item: QTreeWidgetItem):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is not None:
                    items.append(child)
                traverse(child)

        for i in range(self.topLevelItemCount()):
            top_item = self.topLevelItem(i)
            if top_item.data(0, Qt.ItemDataRole.UserRole) is not None:
                items.append(top_item)
            traverse(top_item)

        return items

    def post_filter(self):
        def hide_empty_folders(item: QTreeWidgetItem) -> bool:
            is_empty = True
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is not None:
                    if not child.isHidden():
                        is_empty = False
                else:
                    if not hide_empty_folders(child):
                        is_empty = False

            item.setHidden(is_empty)
            return is_empty

        for i in range(self.topLevelItemCount()):
            top_item = self.topLevelItem(i)
            hide_empty_folders(top_item)

    def current_item_text(self) -> str:
        current_item = self.currentItem()
        if current_item:
            filepath = current_item.data(0, Qt.ItemDataRole.UserRole)
            return filepath if filepath is not None else ""
        return ""

    def is_valid_selection(self):
        current_item = self.currentItem()
        if current_item and current_item.data(0, Qt.ItemDataRole.UserRole) is not None:
            return True
        return False

    def get_item_path(self, item: QTreeWidgetItem) -> str | None:
        return item.data(0, Qt.ItemDataRole.UserRole)
