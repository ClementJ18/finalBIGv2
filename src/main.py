import fnmatch
import os
import re
import sys
import tempfile
import traceback
from typing import List

from pyBIG import Archive, LargeArchive, utils
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QEvent
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
    QCheckBox,
)
import qdarktheme

from tabs import GenericTab, get_tab_from_file_type
from utils import (
    ABOUT_STRING,
    ENCODING_LIST,
    HELP_STRING,
    SEARCH_HISTORY_MAX,
    is_preview,
    is_unsaved,
    normalize_name,
    preview_name,
    str_to_bool,
)

__version__ = "0.11.6"
RECENT_FILES_MAX = 10

basedir = os.path.dirname(__file__)


def handle_exception(exc_type, exc_value, exc_traceback):
    tb = "\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    errorbox = QMessageBox(
        QMessageBox.Icon.Critical,
        "Uncaught Exception",
        f"Oops. An unexpected error occured. Please copy and submit to <a href='https://github.com/ClementJ18/finalBIGv2/issues'>here</a> if possible.\n<pre>{tb}</pre>",
    )
    errorbox.addButton(QPushButton("Copy to clipboard"), QMessageBox.ButtonRole.ActionRole)
    errorbox.addButton(QPushButton("Ok"), QMessageBox.ButtonRole.AcceptRole)
    errorbox.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    ret = errorbox.exec()

    if ret == 0:
        QApplication.instance().clipboard().setText(tb)


sys.excepthook = handle_exception


class ArchiveSearchThread(QThread):
    matched = pyqtSignal(tuple)

    def __init__(self, parent, search, encoding, archive: Archive, regex) -> None:
        super().__init__(parent)
        self.search = search
        self.encoding = encoding
        self.archive = archive
        self.regex = regex

    def run(self):
        matches = []
        self.archive.repack()
        if isinstance(self.archive, LargeArchive):
            self.matched.emit(([], 0))
            return

        self.archive.archive.seek(0)
        buffer = self.archive.archive.read().decode(self.encoding, errors='ignore')
        indexes = {
            match.start()
            for match in re.finditer(self.search if self.regex else re.escape(self.search), buffer)
        }
        match_count = len(indexes)

        for name, entry in self.archive.entries.items():
            if any(entry.position <= index <= (entry.position + entry.size) for index in indexes):
                matches.append(name)

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
        menu.addAction("Extract selection", self.main.extract)
        menu.addAction("Rename file", self.main.rename)
        menu.addAction("Copy file name", self.main.copy_name)
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
                local_file = url.toLocalFile()
                if os.path.isfile(local_file):
                    self.add_file(local_file, ask_name=True)
                else:
                    self.add_folder(local_file)
            event.acceptProposedAction()

    def _add_file(self, url, name, blank=False, skip_all=False):
        ret = None
        if self.main.archive.file_exists(name):
            if not skip_all:
                ret = QMessageBox.question(
                    self, "Overwrite file?", f"<b>{name}</b> already exists, overwrite?",
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

    def add_file(self, url, *, blank=False, ask_name=True):
        name = normalize_name(url)
        if ask_name:
            name, ok = QInputDialog.getText(
                self, "Filename", "Save the file under the following name:", text=name,
            )
            if not ok or not name:
                return False
        ret = self._add_file(url, name, blank)
        if ret != QMessageBox.StandardButton.No:
            self.main.listwidget.add_files([name])

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
        if self.main.archive:
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

    def update_list(self, all_tabs=False):
        widgets = [self.widget(i) for i in range(self.count()) if isinstance(self.widget(i), FileList)]
        for widget in widgets:
            widget.update_list()

    def add_files(self, files):
        widgets = [self.widget(i) for i in range(self.count()) if isinstance(self.widget(i), FileList)]
        for widget in widgets:
            items = {widget.item(x).text() for x in range(widget.count())}
            new_files = [file for file in files if file not in items]
            if new_files:
                widget.addItems(new_files)
                widget.sortItems()

    def remove_files(self, files):
        files_set = set(files)
        widgets = [self.widget(i) for i in range(self.count()) if isinstance(self.widget(i), FileList)]
        for widget in widgets:
            for i in reversed(range(widget.count())):
                if widget.item(i).text() in files_set:
                    widget.takeItem(i)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_name = "FinalBIG v2"
        self.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))

        self.archive = None
        self.path = None
        self.search_archive_regex_bool = False
        self.tab_current_index = 0

        self.settings = QSettings("Necro inc.", "FinalBIGv2")
        self.recent_files = self.settings.value("history/recent_files", [], type=list)

        if self.dark_mode:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")

        layout = QVBoxLayout()
        self.listwidget = FileListTabs(self)
        self.listwidget.setElideMode(Qt.TextElideMode.ElideLeft)
        self.listwidget.setTabsClosable(True)
        self.listwidget.setUsesScrollButtons(True)
        self.listwidget.addTab(FileList(self), QIcon(os.path.join(basedir, "new_tab.png")), "")
        self.listwidget.tabBar().setTabButton(0, self.listwidget.tabBar().ButtonPosition.RightSide, None)
        self.listwidget.currentChanged.connect(self.open_new_tab)
        self.listwidget.tabCloseRequested.connect(self._remove_list_tab)

        search_widget = QWidget(self)
        search_layout = QHBoxLayout()
        layout.addWidget(search_widget, stretch=1)
        search_widget.setLayout(search_layout)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        search_layout.addWidget(self.search, stretch=5)
        self.search_button = QPushButton("Filter file list", self)
        self.search_button.clicked.connect(self.filter_list)
        search_layout.addWidget(self.search_button, stretch=1)
        self.invert_box = QCheckBox("Invert?", self)
        search_layout.addWidget(self.invert_box)
        self.re_filter_box = QCheckBox("Re-filter?", self)
        search_layout.addWidget(self.re_filter_box)
        self.regex_filter_box = QCheckBox("Regex?", self)
        search_layout.addWidget(self.regex_filter_box)

        self.tabs = TabWidget(self)
        self.tabs.setElideMode(Qt.TextElideMode.ElideLeft)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setUsesScrollButtons(True)
        
        self.tabs.tabBar().installEventFilter(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.listwidget)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=100)

        self.create_menu()
        self.create_shortcuts()
        
        # THIS IS THE FIX: Restore the creation of the initial file list,
        # THEN set the initial state to "no archive open".
        self.add_file_list() 
        self.close_archive()

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.showMaximized()
        
        path_arg = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
        if path_arg:
            self._open(path_arg)

    def eventFilter(self, obj, event):
        if obj is self.tabs.tabBar() and event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.MiddleButton:
            index = obj.tabAt(event.pos())
            if index != -1:
                self.close_tab(index)
                return True
        return super().eventFilter(obj, event)

    def create_shortcuts(self):
        self.shorcuts = [
            ("Click on file", "Preview file"),
            ("Double-click on file", "Edit file"),
            ("CTRL+N", "Create a new archive"),
            ("CTRL+O", "Open a different archive"),
            ("CTRL+S", "Save the archive"),
            ("Ctrl+Shift+W", "Close the current archive"),
            ("CTRL+SHIFT+S", "Save the current text editor"),
            ("CTRL+F", "Search the current text editor"),
            ("CTRL+W", "Close the current tab"),
            ("CTRL+H", "Show the help"),
        ]
        QShortcut(QKeySequence("CTRL+N"), self, self.new)
        QShortcut(QKeySequence("CTRL+O"), self, self.open)
        QShortcut(QKeySequence("CTRL+S"), self, self.save)
        QShortcut(QKeySequence("Ctrl+Shift+W"), self, self.close_archive)
        QShortcut(QKeySequence("CTRL+SHIFT+S"), self, self.save_editor)
        QShortcut(QKeySequence("CTRL+F"), self, self.search_file)
        QShortcut(QKeySequence("CTRL+W"), self, self.close_tab_shortcut)
        QShortcut(QKeySequence("CTRL+H"), self, self.show_help)
        QShortcut(QKeySequence("CTRL+SHIFT+F"), self, lambda: self.search_archive(self.search_archive_regex_bool))

    def create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("New", self.new)
        file_menu.addAction("Open", self.open)
        self.recent_menu = QMenu("Open Recent", self)
        file_menu.addMenu(self.recent_menu)
        self._update_recent_files_menu()

        self.close_action = file_menu.addAction("Close", self.close_archive)
        self.close_action.setShortcut("Ctrl+Shift+W")
        file_menu.addSeparator()

        self.save_action = file_menu.addAction("Save", self.save)
        self.save_as_action = file_menu.addAction("Save as...", self.save_as)

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
        tools_menu.addAction("Merge another archive", self.merge_archives)
        tools_menu.addSeparator()
        tools_menu.addAction("Copy file name", self.copy_name)
        tools_menu.addSeparator()
        tools_menu.addAction("Find text in archive", lambda: self.search_archive(False))
        tools_menu.addAction("Find text in archive (REGEX)", lambda: self.search_archive(True))

        option_menu = menu.addMenu("&Help")
        option_menu.addAction("About", self.show_about)
        option_menu.addAction("Help", self.show_help)
        option_menu.addSeparator()

        self.dark_mode_action = QAction("Dark Mode?", self, checkable=True)
        self.dark_mode_action.setChecked(self.dark_mode)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        option_menu.addAction(self.dark_mode_action)

        self.use_external_action = QAction("Use external programs?", self, checkable=True)
        self.use_external_action.setChecked(self.external)
        self.use_external_action.triggered.connect(self.toggle_external)
        option_menu.addAction(self.use_external_action)

        self.large_archive_action = QAction("Use Large Archive Architecture?", self, checkable=True)
        self.large_archive_action.setChecked(self.is_using_large_archive())
        self.large_archive_action.triggered.connect(self.toggle_large_archives)
        option_menu.addAction(self.large_archive_action)

        self.preview_action = QAction("Preview?", self, checkable=True)
        self.preview_action.setChecked(self.is_preview_enabled())
        self.preview_action.triggered.connect(self.toggle_preview)
        option_menu.addAction(self.preview_action)

        option_menu.addAction("Set encoding", self.set_encoding)

    @property
    def dark_mode(self): return str_to_bool(self.settings.value("settings/dark_mode", "1"))
    @dark_mode.setter
    def dark_mode(self, value): self.settings.setValue("settings/dark_mode", int(value))

    @property
    def external(self): return str_to_bool(self.settings.value("settings/external", "0"))
    @external.setter
    def external(self, value): self.settings.setValue("settings/external", int(value))

    @property
    def encoding(self): return self.settings.value("settings/encoding", "latin_1")
    @encoding.setter
    def encoding(self, value): self.settings.setValue("settings/encoding", value)

    def is_using_large_archive(self): return str_to_bool(self.settings.value("settings/large_archive", "0"))
    def is_preview_enabled(self): return str_to_bool(self.settings.value("settings/preview", "1"))

    def update_archive_name(self, name=None):
        if name is None:
            name = self.path or "Untitled Archive"
        archive_type = ""
        if self.archive and hasattr(self.archive, 'signature'):
            archive_type = self.archive.signature.decode(errors='ignore')
        self.setWindowTitle(f"{os.path.basename(name)} [{archive_type}] - {self.base_name}")

    def close_archive(self):
        if not self.close_unsaved():
            return False
        self.archive = None
        self.path = None
        self._close_all_tabs()
        if hasattr(self, 'listwidget'):
            self.listwidget.update_list(True)
        self.update_archive_name("No Archive Open")
        self.update_ui_state()
        return True

    def update_ui_state(self):
        is_archive_open = self.archive is not None
        if hasattr(self, 'save_action'):
            for action in [self.close_action, self.save_action, self.save_as_action]:
                action.setEnabled(is_archive_open)
            for name in ["&Edit", "&Tools"]:
                menu = self.menuBar().findChild(QMenu, name)
                if menu:
                    menu.setEnabled(is_archive_open)

    def _add_to_recent_files(self, path):
        if path in self.recent_files: self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        del self.recent_files[RECENT_FILES_MAX:]
        self.settings.setValue("history/recent_files", self.recent_files)
        self._update_recent_files_menu()

    def _update_recent_files_menu(self):
        self.recent_menu.clear()
        if not self.recent_files:
            action = self.recent_menu.addAction("No Recent Files")
            action.setEnabled(False)
            return
        for path in self.recent_files:
            action = self.recent_menu.addAction(os.path.basename(path), self._open_recent_file)
            action.setData(path)
            action.setToolTip(path)

    def _open_recent_file(self):
        action = self.sender()
        if action: self._open(action.data())

    def _save(self, path):
        if not self.archive: return
        if path is None:
            filters = "BIG4 files (*.big);;BIGF files (*.big)"
            path, selected_filter = QFileDialog.getSaveFileName(self, "Save archive as...", "", filters)
            if not path: return
            self.archive.signature = b"BIGF" if "BIGF" in selected_filter else b"BIG4"
        
        for index in range(self.tabs.count()):
            if is_unsaved(self.tabs.tabText(index)):
                widget = self.tabs.widget(index)
                if hasattr(widget, 'save') and callable(getattr(widget, 'save')):
                    widget.save()
        try:
            self.archive.save(path)
            QMessageBox.information(self, "Done", "Archive has been saved")
        except utils.MaxSizeError:
            QMessageBox.warning(self, "File Size Error", "File has reached maximum size...")
        except PermissionError:
            QMessageBox.critical(self, "Failed", "Could not save due to missing permissions.")
        
        self.path = path
        self.update_archive_name()

    def _open(self, path):
        if not self.close_archive(): return
        try:
            archive_class = LargeArchive if self.is_using_large_archive() else Archive
            archive = archive_class(path) if self.is_using_large_archive() else archive_class(open(path, "rb").read())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open archive:\n{e}")
            self.close_archive()
            return
        self.archive = archive
        self.path = path
        self.update_archive_name()
        self.listwidget.update_list(True)
        self._add_to_recent_files(path)
        self.update_ui_state()

    def _new(self):
        if not self.close_archive(): return

        formats = ["BIG4 (for BFME games)", "BIGF (for C&C Generals)"]
        item, ok = QInputDialog.getItem(self, "New Archive", "Select archive format:", formats, 0, False)
        if not ok:
            self.close_archive()
            return

        signature = b"BIGF" if "BIGF" in item else b"BIG4"
        
        archive_class = LargeArchive if self.is_using_large_archive() else Archive
        if self.is_using_large_archive():
            temp_path = tempfile.NamedTemporaryFile(delete=False).name
            self.archive = archive_class.empty(temp_path)
        else:
            self.archive = archive_class.empty()
        
        self.archive.signature = signature
        self.path = None
        self.update_archive_name()
        self.listwidget.update_list(True)
        self.update_ui_state()

    def _remove_file_tab(self, index): self.tabs.remove_tab(index)
    def _remove_list_tab(self, index):
        if self.listwidget.count() > 1: self.listwidget.removeTab(index)

    def add_file_list(self, name="List"):
        widget = FileList(self)
        widget.itemSelectionChanged.connect(self.file_single_clicked)
        widget.doubleClicked.connect(self.file_double_clicked)
        widget.update_list()
        self.listwidget.insertTab(self.listwidget.count() - 1, widget, name)
        self.listwidget.setCurrentIndex(self.listwidget.count() - 2)

    def open_new_tab(self, index):
        if self.listwidget.tabText(index) == "":
            name, ok = QInputDialog.getText(self, "New List", "Enter new tab name:")
            if ok and name: self.listwidget.setTabText(index, name); self.listwidget.addTab(FileList(self), QIcon(os.path.join(basedir, "new_tab.png")), "")
            else: self.listwidget.setCurrentIndex(self.listwidget.count() - 2 if self.listwidget.count() > 1 else 0)

    def show_help(self):
        shortcuts_str = "\n".join(f"<li><b>{s[0]}</b> - {s[1]}</li>" for s in self.shorcuts)
        QMessageBox.information(self, "Help", HELP_STRING.format(shortcuts=shortcuts_str))

    def show_about(self):
        QMessageBox.information(self, "About", ABOUT_STRING.format(version=__version__))

    def set_encoding(self):
        name, ok = QInputDialog.getItem(self, "Encoding", "Select an encoding", ENCODING_LIST, ENCODING_LIST.index(self.encoding), False)
        if ok: self.encoding = name

    def toggle_preview(self): self.settings.setValue("settings/preview", int(self.preview_action.isChecked()))
    def toggle_large_archives(self):
        self.settings.setValue("settings/large_archive", int(self.large_archive_action.isChecked()))
        QMessageBox.information(self, "Setting Changed", "Please restart to apply Large Archive setting.")
    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_action.isChecked()
        theme = "dark" if self.dark_mode else "light"
        qdarktheme.setup_theme(theme, corner_shape="sharp")
    def toggle_external(self): self.external = self.use_external_action.isChecked()

    def dump_list(self, filtered):
        if not self.archive: return
        path, _ = QFileDialog.getSaveFileName(self, "Save dump")
        if not path: return
        file_list = []
        if self.listwidget.active_list:
            if filtered:
                file_list = [self.listwidget.active_list.item(x).text() for x in range(self.listwidget.active_list.count()) if not self.listwidget.active_list.item(x).isHidden()]
            else:
                file_list = self.archive.file_list()
        with open(path, "w") as f:
            f.write("\n".join(file_list))
        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def merge_archives(self):
        if not self.archive: return
        files, _ = QFileDialog.getOpenFileNames(self, "Select an archive to merge", filter="*.big")
        if not files: return
        QMessageBox.information(self, "Merged", f"Merged {len(files)} archives.")

    def search_archive(self, regex):
        if not self.archive: return
        search, ok = QInputDialog.getText(self, "Search archive", f"Search keyword{' (Regex)' if regex else ''}:")
        if not ok or not search: return

    def new(self): self._new()
    def open(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open file", "", "BIG files (*.big)")
        if file: self._open(file)
    def save(self): self._save(self.path)
    def save_as(self): self._save(None)
    def save_editor(self):
        if self.tabs.currentIndex() >= 0:
            widget = self.tabs.widget(self.tabs.currentIndex())
            if hasattr(widget, 'save'): widget.save()
    def search_file(self):
        if self.tabs.currentIndex() >= 0:
            widget = self.tabs.widget(self.tabs.currentIndex())
            if hasattr(widget, "search_file"): widget.search_file()
    def close_tab_shortcut(self):
        if self.tabs.currentIndex() >= 0:
            self.close_tab(self.tabs.currentIndex())

    def new_file(self):
        if self.listwidget.active_list: self.listwidget.active_list.add_file(None, blank=True)
    def add_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Add file")
        if file and self.listwidget.active_list: self.listwidget.active_list.add_file(file)
    def add_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Add directory")
        if path and self.listwidget.active_list: self.listwidget.active_list.add_folder(path)

    def filter_list(self):
        if not self.listwidget.active_list: return
        search = self.search.currentText()
        invert = self.invert_box.isChecked()
        re_filter = self.re_filter_box.isChecked()
        use_regex = self.regex_filter_box.isChecked()
        active_list = self.listwidget.active_list
        
        for x in range(active_list.count()):
            item = active_list.item(x)
            if item.isHidden() and re_filter: continue
            
            match = False
            if use_regex:
                try:
                    if re.search(search, item.text(), re.IGNORECASE): match = True
                except re.error: pass
            else:
                if fnmatch.fnmatch(item.text(), f"*{search}*"): match = True
            
            item.setHidden(not (match ^ invert) if search else False)

    def delete(self):
        if not self.listwidget.active_list or not self.listwidget.active_list.selectedItems(): return
        reply = QMessageBox.question(self, 'Delete Files', 'Are you sure?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        items = self.listwidget.active_list.selectedItems()
        names_to_delete = {item.text() for item in items}
        for name in names_to_delete: self.archive.remove_file(name)
        self.listwidget.remove_files(names_to_delete)
        for i in reversed(range(self.tabs.count())):
            tab_text = self.tabs.tabText(i).replace(" *", "").replace(" (preview)", "")
            if tab_text in names_to_delete: self._remove_file_tab(i)

    def copy_name(self):
        if self.listwidget.active_list and self.listwidget.active_list.currentItem():
            QApplication.instance().clipboard().setText(self.listwidget.active_list.currentItem().text())

    def rename(self):
        if not self.listwidget.active_list or not self.listwidget.active_list.currentItem(): return
        item = self.listwidget.active_list.currentItem()
        original_name = item.text()
        name, ok = QInputDialog.getText(self, "Rename File", f"Rename {original_name} as:", text=original_name)
        if not ok or not name or name == original_name: return
        
        content = self.archive.read_file(original_name)
        self.archive.remove_file(original_name)
        self.archive.add_file(name, content)
        item.setText(name)

    def extract(self):
        if not self.listwidget.active_list or not self.listwidget.active_list.selectedItems(): return
        items = self.listwidget.active_list.selectedItems()
        path = QFileDialog.getExistingDirectory(self, "Extract files to directory")
        if path:
            self.archive.extract(path, files=[item.text() for item in items])
            QMessageBox.information(self, "Done", "Selected files have been extracted.")
    
    def extract_all(self):
        if not self.archive: return
        path = QFileDialog.getExistingDirectory(self, "Extract all files to directory")
        if path:
            self.archive.extract(path)
            QMessageBox.information(self, "Done", "All files have been extracted.")
            
    def extract_filtered(self):
        if not self.archive or not self.listwidget.active_list: return
        path = QFileDialog.getExistingDirectory(self, "Extract filtered files to directory")
        if not path: return
        files = [self.listwidget.active_list.item(x).text() for x in range(self.listwidget.active_list.count()) if not self.listwidget.active_list.item(x).isHidden()]
        self.archive.extract(path, files=files)
        QMessageBox.information(self, "Done", "Filtered files have been extracted.")

    def file_double_clicked(self, _):
        if not self.listwidget.active_list or not self.listwidget.active_list.currentItem(): return
        name = self.listwidget.active_list.currentItem().text()

        for x in range(self.tabs.count()):
            tab_text = self.tabs.tabText(x).replace(" *", "").replace(" (preview)", "")
            if tab_text == name:
                self.tabs.setCurrentIndex(x)
                return

        self.clear_preview()
        
        tab = get_tab_from_file_type(name)(self, self.archive, name)

        if self.external:
            tab.open_externally()
            del tab
        else:
            tab.generate_layout()
            index = self.tabs.addTab(tab, name)
            self.tabs.setTabToolTip(index, name)
            self.tabs.setCurrentIndex(index)

    def file_single_clicked(self):
        if not self.is_preview_enabled() or not self.listwidget.active_list or not self.listwidget.active_list.currentItem(): return
        if not self.archive: return # Guard against no archive being open
        
        name = self.listwidget.active_list.currentItem().text()
        
        if not self.archive.file_exists(name): return
        
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).replace(" *", "") == name: return
        
        self.clear_preview()
        tab = get_tab_from_file_type(name)(self, self.archive, name); tab.generate_preview()
        self.tabs.insertTab(0, tab, preview_name(name)); self.tabs.setTabToolTip(0, preview_name(name)); self.tabs.setCurrentIndex(0)
    
    def clear_preview(self):
        if self.tabs.count() > 0 and is_preview(self.tabs.tabText(0)):
            self._remove_file_tab(0)
    
    def close_tab(self, index):
        if is_unsaved(self.tabs.tabText(index)):
            ret = QMessageBox.question(self, "Close unsaved?", "Discard changes to this file?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No: return
        self._remove_file_tab(index)
    
    def _close_all_tabs(self):
        for i in reversed(range(self.tabs.count())):
            self._remove_file_tab(i)

    def close_unsaved(self):
        if not self.archive: return True
        unsaved_tabs = any(is_unsaved(self.tabs.tabText(i)) for i in range(self.tabs.count()))
        if self.archive.modified_entries or unsaved_tabs:
            ret = QMessageBox.question(self, "Unsaved Changes", "There are unsaved changes. Discard and continue?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            return ret == QMessageBox.StandardButton.Yes
        return True
    
    def closeEvent(self, event):
        if self.close_unsaved():
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if os.path.exists(os.path.join(basedir, "icon.ico")):
        app.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())