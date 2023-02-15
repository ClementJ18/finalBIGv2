import fnmatch
import os
import re
import sys
import logging

from pyBIG import Archive
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
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
from utils import ABOUT_STRING, ENCODING_LIST, HELP_STRING, SEARCH_HISTORY_MAX, is_preview, is_unsaved, normalize_name, preview_name, str_to_bool

__version__ = "0.3.0"

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

class ArchiveSearchThread(QThread):
    matched = pyqtSignal(tuple)

    def __init__(self, parent, search, encoding, archive) -> None:
        super().__init__(parent)

        self.search = search
        self.encoding = encoding
        self.archive = archive

    def run(self):
        matches = []
        self.archive.repack()

        self.archive.archive.seek(0)
        buffer = self.archive.archive.read().decode(self.encoding)
        indexes = {match.start() for match in re.finditer(self.search, buffer)}
        match_count = len(indexes)
        
        for name, entry in self.archive.entries.items():
            matched_indexes = {index for index in indexes if entry.position <= index <= (entry.position + entry.size)}
            if matched_indexes:
                indexes -= matched_indexes
                matches.append(name)
                continue

        self.matched.emit((matches, match_count))

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
        menu.addAction("Copy name", self.main.copy_name)

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

        self.settings = QSettings("Necro inc.", "FinalBIGv2")

        if self.dark_mode:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")


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
        tools_menu.addAction("Dump entire file list", lambda: self.dump_list(False))
        tools_menu.addAction("Dump filtered file list", lambda: self.dump_list(True))
        tools_menu.addAction("Copy file name", self.copy_name)
        tools_menu.addAction("Find text in archive", self.search_archive)

        option_menu = menu.addMenu("&Help")
        option_menu.addAction("About", self.show_about)
        option_menu.addAction("Help", self.show_help)

        option_menu.addSeparator()

        self.dark_mode_action = QAction("Dark Mode?", self, checkable=True)
        self.dark_mode_action.setChecked(self.dark_mode)
        option_menu.addAction(self.dark_mode_action)
        option_menu.triggered.connect(self.toggle_dark_mode)

        self.preview_action = QAction("Preview?", self, checkable=True)
        self.preview_action.setChecked(str_to_bool(self.settings.value("settings/preview", "1")))
        option_menu.addAction(self.preview_action)
        option_menu.triggered.connect(self.toggle_preview)

        option_menu.addAction("Set encoding", self.set_encoding)

    @property
    def dark_mode(self):
        return str_to_bool(self.settings.value("settings/dark_mode", "1"))

    @dark_mode.setter
    def dark_mode_setter(self, value):
        self.settings.setValue("settings/dark_mode", int(value))
        self.settings.sync()

    @property
    def encoding(self):
        return self.settings.value("settings/encoding", "latin_1")

    @encoding.setter
    def encoding_setter(self, value):
        self.settings.setValue("settings/encoding", value)
        self.settings.sync()

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

    def set_encoding(self):
        name, ok = QInputDialog.getItem(self, "Encoding", "Select an encoding", ENCODING_LIST, ENCODING_LIST.index(self.encoding), False)
        if not ok:
            return

        self.encoding = name

    def toggle_preview(self):
        self.settings.setValue("settings/preview", int(self.preview_action.isChecked()))
        self.settings.sync()

    def toggle_dark_mode(self):
        is_checked = self.dark_mode_action.isChecked()
        
        self.dark_mode = is_checked
        
        if is_checked:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")

        for x in range(self.tabs.count()):
            widget = self.tabs.widget(x)
            if hasattr(widget, "text_widget"):
                widget.text_widget.toggle_dark_mode(is_checked)

    def dump_list(self, filtered):
        file = QFileDialog.getSaveFileName(self, "Save dump")[0]
        if not file:
            return

        if filtered:
            file_list = (self.listwidget.item(x).text() for x in range(self.listwidget.count()) if not self.listwidget.item(x).isHidden())
        else:
            file_list = self.archive.file_list()

        with open(file, "w") as f:
            f.write("\n".join(file_list))

        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def search_archive(self):
        search, ok = QInputDialog.getText(
            self, "Filename", f"Search keyword (Regex)"   
        )
        if not ok:
            return

        def update_list_with_matches(returned):
            matches = returned[0]
            for x in range(self.listwidget.count()):
                item = self.listwidget.item(x)
                item.setHidden(item.text() not in matches)

            self.message_box.done(1)
            QMessageBox.information(self, "Search finished", f"Found <b>{returned[1]}</b> instances over <b>{len(matches)}</b> files. Filtering list.")


        self.message_box = QMessageBox(QMessageBox.Icon.Information, "Search in progress", "Searching the archive, please wait...", QMessageBox.StandardButton.Ok, self)
        self.message_box.button(QMessageBox.StandardButton.Ok).setEnabled(False)

        self.thread = ArchiveSearchThread(self, search, self.encoding, self.archive)
        self.thread.matched.connect(update_list_with_matches)
        self.thread.start()
        self.message_box.exec()

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
        
        deleted = []
        skip_all = False
        for item in self.listwidget.selectedItems():
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

            deleted.append((name, preview_name(name)))
            self.archive.remove_file(name)
        
        if not deleted:
            return

        for i in reversed(range(self.tabs.count())):
            name = self.tabs.tabText(i)
            if (name in t for t in deleted):
                self.tabs.remove_tab(i)

        self.listwidget.update_list()
        QMessageBox.information(self, "Done", "File selection has been deleted")

    def clear_preview(self):
        if self.tabs.count() < 0:
            return

        name = self.tabs.tabText(0)
        if is_preview(name):
            self._remove_tab(0)

    def copy_name(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.currentItem().text()
        app.clipboard().setText(original_name)

    def rename(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.currentItem().text()

        name, ok = QInputDialog.getText(
            self, "Filename", f"Rename {original_name} as:", text=original_name   
        )
        if not ok:
            return

        for i in reversed(range(self.tabs.count())):
            tab_name = self.tabs.tabText(i)
            if tab_name in (preview_name(name), name):
                self.tabs.remove_tab(i)

        self.archive.add_file(name, self.archive.read_file(original_name))
        self.archive.remove_file(original_name)

        self.listwidget.update_list()
        QMessageBox.information(self, "Done", "File renamed")

    def extract(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.selectedItems()
        
        extracted_one = False
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

            extracted_one = True

        if extracted_one:
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
            index = self.tabs.count() - 1
            self.tabs.setTabToolTip(index, name)
            self.tabs.setCurrentIndex(index)

            if self.tabs.tabText(0) == preview_name(name):
                self._remove_tab(0)

    def file_single_clicked(self):
        if not str_to_bool(self.settings.value("settings/preview", "1")):
            return

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

            if is_preview(self.tabs.tabText(0)) and self.tabs.currentIndex() >= 0:
                self._remove_tab(0)

            self.tabs.insertTab(0, tab, preview_name(name))
            self.tabs.setTabToolTip(0, preview_name(name))
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
    
    app.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))

    w.show()
    sys.exit(app.exec())
