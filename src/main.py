import fnmatch
import os
import sys
import logging

from pyBIG import Archive
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QAction
from PyQt6.QtWidgets import (
    QMenu,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
import qdarktheme

from tabs import get_tab_from_file_type
from utils import ABOUT_STRING, HELP_STRING, SEARCH_HISTORY_MAX, is_preview, is_unsaved, normalize_name, preview_name

__version__ = "0.1.8"

basedir = os.path.dirname(__file__)
logger = logging.getLogger("FinalBIGv2")
logger.setLevel(logging.ERROR)

ch_file = logging.FileHandler("error.log", mode="a+", delay=True)
ch_file.setLevel(logging.ERROR)

logger.addHandler(ch_file)


def handle_exception(exc_type, exc_value, exc_traceback):
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = handle_exception


class FileList(QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        self.main: MainWindow = parent

    def context_menu(self, pos):
        global_position = self.mapToGlobal(pos)
         
        menu = QMenu(self)
        menu.addAction("Delete selection", self.main.delete)
        menu.addAction("Rename file", self.main.rename)
        menu.addAction("Extract selection", self.main.extract)

        menu.exec(global_position)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if os.path.isfile(url.toLocalFile()):
                    self.add_file(url.toLocalFile())
                else:
                    self.add_folder(url.toLocalFile())

            self.update_list()
            event.acceptProposedAction()

    def _add_file(self, url, name, blank=False, skip_all=False):
        ret = None
        if self.main.archive.file_exists(name):
            if not skip_all:
                ret = QMessageBox.question(
                    self,
                    "Overwrite file?",
                    f"<b>{name}</b> already exists, overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.YesToAll,
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

    def add_file(self, url, blank=False):
        name, ok = QInputDialog.getText(
            self, "Filename", "Save the file under the following name:", text=normalize_name(url)   
        )
        if not ok:
            return False

        self._add_file(url, name, blank)

    def add_folder(self, url):
        skip_all = False
        common_dir = os.path.dirname(url)
        for root, _, files in os.walk(url):
            for f in files:
                full_path = os.path.join(root, f)
                name = normalize_name(os.path.relpath(full_path, common_dir))
                ret = self._add_file(full_path, name, blank=False, skip_all=skip_all)

                if ret == QMessageBox.StandardButton.YesToAll:
                    skip_all = True

    def update_list(self):
        self.clear()
        for index, entry in enumerate(self.main.archive.file_list()):
            self.insertItem(index, entry)

        self.main.filter_list()

class TabWidget(QTabWidget):
    def remove_tab(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()
    
        self.removeTab(index)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_name = "FinalBIG v2"
        self.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))

        self.dark_mode = False

        layout = QVBoxLayout()

        self.listwidget = FileList(self)
        self.listwidget.itemSelectionChanged.connect(self.file_single_clicked)
        self.listwidget.doubleClicked.connect(self.file_double_clicked)

        search_widget = QWidget(self)
        search_layout = QHBoxLayout()
        layout.addWidget(search_widget, stretch=1)
        search_widget.setLayout(search_layout)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        search_layout.addWidget(self.search, stretch=5)

        self.search_button = QPushButton(self)
        self.search_button.setText("Filter file list")
        self.search_button.clicked.connect(self.filter_list)
        search_layout.addWidget(self.search_button, stretch=1)

        self.tabs = TabWidget(self)
        self.tabs.setElideMode(Qt.TextElideMode.ElideLeft)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setUsesScrollButtons(True)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self.listwidget)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 200)
        layout.addWidget(splitter, stretch=100)

        self.create_menu()
        self.create_shortcuts()

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.showMaximized()

        try:
            path_arg = sys.argv[1]
        except IndexError:
            path_arg = ""

        if os.path.exists(path_arg):
            self._open(path_arg)
        else:
            self._new()

    def create_shortcuts(self):
        self.shorcuts = [
            (
                "Click on file",
                "Preview file"
            ),
            (
                "Double-click on file",
                "Edit file"
            ),
            (
                "Left-click drag",
                "Select multiple files"
            ),
            (
                "Right-click on file/selection",
                "Context menu"
            ),
            (
                QShortcut(QKeySequence("CTRL+N",),self,self.new,),
                "Create a new archive",
            ),
            (
                QShortcut(QKeySequence("CTRL+O"), self, self.open), 
                "Open a different archive"
            ),
            (
                QShortcut(QKeySequence("CTRL+S"), self, self.save), 
                "Save the archive"
            ),
            (
                QShortcut(QKeySequence("CTRL+SHIFT+S"), self, self.save_editor),
                "Save the current text editor",
            ),
            (
                QShortcut(QKeySequence("CTRL+RETURN"), self, self.filter_list),
                "Filter the list with the current search",
            ),
            (
                QShortcut(QKeySequence("CTRL+F"), self, self.search_file),
                "Search the current text editor",
            ),
            (
                QShortcut(QKeySequence("CTRL+W"), self, self.close_tab_shortcut), 
                "Close the current tab"
            ),
            (
                "CTRL+;",
                "Comment/uncomment the currently selected text",
            ),
            (
                QShortcut(QKeySequence("CTRL+H"), self, self.show_help),
                "Show the help",
            ),
        ]

    def create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("New", self.new)
        file_menu.addAction("Open", self.open)
        file_menu.addAction("Save", self.save)
        file_menu.addAction("Save as...", self.save_as)

        edit_menu = menu.addMenu("&Edit")
        edit_menu.addAction("New file", self.new_file)
        edit_menu.addAction("Add file", self.add_file)
        edit_menu.addAction("Add directory", self.add_directory)
        edit_menu.addAction("Delete selection", self.delete)
        edit_menu.addAction("Rename file", self.rename)

        edit_menu.addSeparator()

        edit_menu.addAction("Extract selection", self.extract)
        edit_menu.addAction("Extract all", self.extract_all)
        edit_menu.addAction("Extract filtered", self.extract_filtered)

        tools_menu = menu.addMenu("&Tools")
        tools_menu.addAction("Dump file list", self.dump_list)

        option_menu = menu.addMenu("&Help")
        option_menu.addAction("About", self.show_about)
        option_menu.addAction("Help", self.show_help)

        option_menu.addSeparator()

        self.dark_mode_action = QAction("Dark Mode", self, checkable=True)
        option_menu.addAction(self.dark_mode_action)
        option_menu.triggered.connect(self.toggle_dark_mode)

    def is_file_selected(self):
        if not self.listwidget.selectedItems():
            QMessageBox.warning(self, "No file selected", "You have not selected a file")
            return False

        return True

    def update_archive_name(self, name=None):
        if name is None:
            name = self.path or "Untitled Archive"

        self.setWindowTitle(f"{os.path.basename(name)} - {self.base_name}")

    def _save(self, path):
        if path is None:
            path = QFileDialog.getSaveFileName(self, "Save archive", "", "BIG files (*.big)")[0]

        if not path:
            return

        for index in range(self.tabs.count()):
            if is_unsaved(self.tabs.tabText(index)):
                self.tabs.widget(index).save()

        self.archive.save(path)
        QMessageBox.information(self, "Done", "Archive has been saved")
        self.path = path
        self.update_archive_name()

    def _open(self, path):
        try:
            self.path = path
            with open(self.path, "rb") as f:
                self.archive = Archive(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

        self.update_archive_name()
        self.listwidget.update_list()

    def _new(self):
        self.archive = Archive()
        self.path = None
        self.listwidget.update_list()
        self.update_archive_name()

    def _remove_tab(self, index):
        self.tabs.remove_tab(index)

    def show_help(self):
        string = HELP_STRING.format(
            shortcuts="\n".join(
                f"<li><b>{s[0] if isinstance(s[0], str) else s[0].key().toString()}</b> - {s[1]} </li>" for s in self.shorcuts
            )
        )
        QMessageBox.information(self, "Help", string)

    def show_about(self):
        QMessageBox.information(self, "About", ABOUT_STRING.format(version=__version__))

    def toggle_dark_mode(self):
        if self.dark_mode_action.isChecked():
            qdarktheme.setup_theme("dark", corner_shape="sharp")
            self.dark_mode = True
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")
            self.dark_mode = False

        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, "text_widget"):
                widget.text_widget.toggle_dark_mode(self.dark_mode)

    def dump_list(self):
        file = QFileDialog.getSaveFileName(self, "Save dump")[0]
        if not file:
            return

        with open(file, "w") as f:
            f.write("\n".join(name for name in self.archive.file_list()))

        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def new(self):
        if not self.close_unsaved():
            return

        self._new()

    def open(self):
        if not self.close_unsaved():
            return

        file = QFileDialog.getOpenFileName(self, "Open file", "", "BIG files (*.big)")[0]
        if not file:
            return

        self._open(file)

    def save(self):
        self._save(self.path)

    def save_as(self):
        self._save(None)

    def save_editor(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        self.tabs.widget(index).save()

    def search_file(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        widget = self.tabs.widget(index)
        if hasattr(widget, "search_file"):
            widget.search_file()

    def add_file(self):
        file = QFileDialog.getOpenFileName(self, "Add file")[0]
        if not file:
            return

        self.listwidget.add_file(file)
        self.listwidget.update_list()

    def add_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Add directory")
        if not path:
            return

        self.listwidget.add_folder(path)
        self.listwidget.update_list()

    def new_file(self):
        self.listwidget.add_file(None, blank=True)
        self.listwidget.update_list()

    def filter_list(self):
        search = self.search.currentText()
        for x in range(self.listwidget.count()):
            item = self.listwidget.item(x)

            if search == "":
                item.setHidden(False)
            else:
                item.setHidden(not fnmatch.fnmatchcase(item.text(), search))

        if search == "":
            return

        if not any(self.search.itemText(x) == search for x in range(self.search.count())):
            self.search.addItem(search)

        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

    def delete(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.selectedItems()

        skip_all = False
        for item in items:
            name = item.text()
            if not skip_all:
                ret = QMessageBox.question(
                    self,
                    "Delete file?",
                    f"Are you sure you want to delete <b>{name}</b>?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.YesToAll,
                    QMessageBox.StandardButton.No,
                )
                if ret == QMessageBox.StandardButton.No:
                    continue

                if ret == QMessageBox.StandardButton.YesToAll:
                    skip_all = True

            self.archive.remove_file(name)

        self.listwidget.update_list()
        QMessageBox.information(self, "Done", "File selection has been deleted")

    def clear_preview(self):
        if self.tabs.count() < 0:
            return

        name = self.tabs.tabText(0)
        if is_preview(name):
            self._remove_tab(0)

    def rename(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.currentItem().text()

        name, ok = QInputDialog.getText(
            self, "Filename", f"Rename {original_name} as:", text=original_name   
        )
        if not ok:
            return

        self.clear_preview()

        self.archive.add_file(name, self.archive.read_file(original_name))
        self.archive.remove_file(original_name)

        self.listwidget.update_list()
        QMessageBox.information(self, "Done", "File renamed")

    def extract(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.selectedItems()
        
        for item in items:
            name = item.text()
            file_name = name.split("\\")[-1]
            path = QFileDialog.getSaveFileName(
                self, "Extract file", file_name
            )[0]
            if not path:
                continue

            with open(path, "wb") as f:
                f.write(self.archive.read_file(name))

        QMessageBox.information(self, "Done", "File selection has been extracted")

    def extract_all(self):
        path = QFileDialog.getExistingDirectory(
            self, "Extract all files to directory"
        )
        if not path:
            return

        self.archive.extract(path)
        QMessageBox.information(self, "Done", "All files have been extracted")

    def extract_filtered(self):
        path = QFileDialog.getExistingDirectory(
            self, "Extract filtered files to directory"
        )
        if not path:
            return

        files = [self.listwidget.item(x).text() for x in range(self.listwidget.count()) if not self.listwidget.item(x).isHidden()]

        self.archive.extract(path, files=files)
        QMessageBox.information(self, "Done", "Filtered files have been extracted")

    def file_double_clicked(self, _):
        name = self.listwidget.currentItem().text()

        for x in range(self.tabs.count()):
            if self.tabs.tabText(x) == name:
                self.tabs.setCurrentIndex(x)
                break
        else:
            tab = get_tab_from_file_type(name)(self, self.archive, name)
            tab.generate_layout()

            self.tabs.addTab(tab, name)
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

            if self.tabs.tabText(0) == preview_name(name):
                self._remove_tab(0)

    def file_single_clicked(self):
        name = self.listwidget.currentItem().text()
        if not self.archive.file_exists(name):
            return

        for x in range(self.tabs.count()):
            if self.tabs.tabText(x) == name:
                self.tabs.setCurrentIndex(x)
                break
        else:
            tab = get_tab_from_file_type(name)(self, self.archive, name)
            tab.generate_preview()

            if self.tabs.currentIndex() < 0:
                self.tabs.addTab(tab, preview_name(name))
                return

            if is_preview(self.tabs.tabText(0)):
                self._remove_tab(0)

            self.tabs.insertTab(0, tab, preview_name(name))
            self.tabs.setCurrentIndex(0)
        

    def close_tab_shortcut(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        self.close_tab(index)

    def close_tab(self, index):
        if is_unsaved(self.tabs.tabText(index)):
            ret = QMessageBox.question(
                self,
                "Close unsaved?",
                "There is unsaved work, are you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.No:
                return

        self._remove_tab(index)

    def close_unsaved(self):
        unsaved_tabs = any(is_unsaved(self.tabs.tabText(i)) for i in range(self.tabs.count()))
        if self.archive.modified_entries or unsaved_tabs:
            ret = QMessageBox.question(
                self,
                "Close unsaved?",
                "There is unsaved work, are you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.No:
                return False

        for t in range(self.tabs.count()):
            self._remove_tab(t)

        return True

    def closeEvent(self, event):
        if self.close_unsaved():
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()

    qdarktheme.setup_theme("auto", corner_shape="sharp")
    
    app.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))

    w.show()
    sys.exit(app.exec())
