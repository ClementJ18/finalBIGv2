import fnmatch
import os
import re
import sys
import tempfile
import traceback
from typing import List

from pyBIG import Archive, LargeArchive, utils
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

__version__ = "0.11.0"

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
        app.clipboard().setText(tb)


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

        self.archive.archive.seek(0)
        buffer = self.archive.archive.read().decode(self.encoding)
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
                if os.path.isfile(url.toLocalFile()):
                    self.add_file(url.toLocalFile())
                else:
                    self.add_folder(url.toLocalFile())

            event.acceptProposedAction()

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
            if not ok:
                return False

        ret = self._add_file(url, name, blank)
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
        for index, entry in enumerate(self.main.archive.file_list()):
            self.insertItem(index, entry)

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
        return [self.widget(i) for i in range(self.count() - 1)]

    @property
    def all_but_active(self) -> List[FileList]:
        return [self.widget(i) for i in range(self.count() - 1) if i != self.currentIndex()]

    def update_list(self, all=False):
        to_update = self.all_lists if all else [self.active_list]
        for widget in to_update:
            widget.update_list()

    def add_files(self, files, replace=False):
        # expressions = f"^({'|'.join([f for f in files])})$".replace("\\", "\\\\")

        for widget in self.all_lists:
            # items = [x.text() for x in widget.findItems(expressions, Qt.MatchFlag.MatchRegularExpression)]
            items = [widget.item(x).text() for x in range(widget.count())]
            widget.insertItems(widget.count(), [file for file in files if file not in items])
            widget.sortItems()

    def remove_files(self, files):
        for widget in self.all_lists:
            for x in range(widget.count()):
                item = widget.item(x)
                if item.text() in files:
                    widget.takeItem(widget.row(item))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_name = "FinalBIG v2"
        self.setWindowIcon(QIcon(os.path.join(basedir, "icon.ico")))

        self.search_archive_regex_bool = False
        self.tab_current_index = 0

        self.settings = QSettings("Necro inc.", "FinalBIGv2")

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
        self.listwidget.tabBar().setTabButton(
            0, self.listwidget.tabBar().ButtonPosition.RightSide, None
        )

        self.listwidget.currentChanged.connect(self.open_new_tab)
        self.listwidget.tabCloseRequested.connect(self._remove_list_tab)

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

        self.invert_box = QCheckBox("Invert?", self)
        self.invert_box.setToolTip("Filter based on names that do <b>NOT</b> match?")
        search_layout.addWidget(self.invert_box)

        self.re_filter_box = QCheckBox("Re-filter?", self)
        self.re_filter_box.setToolTip(
            "Apply the new filter on the current list rather than clearing previous filters"
        )
        search_layout.addWidget(self.re_filter_box)

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

        try:
            path_arg = sys.argv[1]
        except IndexError:
            path_arg = ""

        if os.path.exists(path_arg):
            self._open(path_arg)
        else:
            self._new()

        self.add_file_list()

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.showMaximized()

    def create_shortcuts(self):
        self.shorcuts = [
            ("Click on file", "Preview file"),
            ("Double-click on file", "Edit file"),
            ("Left-click drag", "Select multiple files"),
            ("Right-click on file/selection", "Context menu"),
            (
                QShortcut(
                    QKeySequence("CTRL+N"),
                    self,
                    self.new,
                ),
                "Create a new archive",
            ),
            (
                QShortcut(QKeySequence("CTRL+O"), self, self.open),
                "Open a different archive",
            ),
            (QShortcut(QKeySequence("CTRL+S"), self, self.save), "Save the archive"),
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
                "Close the current tab",
            ),
            (
                "CTRL+;",
                "Comment/uncomment the currently selected text",
            ),
            (
                QShortcut(QKeySequence("CTRL+H"), self, self.show_help),
                "Show the help",
            ),
            (
                QShortcut(
                    QKeySequence("CTRL+SHIFT+F"),
                    self,
                    lambda: self.search_archive(self.search_archive_regex_bool),
                ),
                "Search for text in the archive",
            ),
            (
                QShortcut(QKeySequence("ALT+R"), self, self.toggle_search_archive_regex),
                "Toggle the 'Search for text in archive' shortcut regex search on/off",
            ),
        ]

    def toggle_search_archive_regex(self):
        self.search_archive_regex_bool = not self.search_archive_regex_bool

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
        self.dark_mode_action.setToolTip("Whether to use dark mode or not")
        self.dark_mode_action.setChecked(self.dark_mode)
        option_menu.addAction(self.dark_mode_action)
        option_menu.triggered.connect(self.toggle_dark_mode)

        self.use_external_action = QAction("Use external programs?", self, checkable=True)
        self.use_external_action.setToolTip(
            "Whether to open using the internal editor or the user's default application"
        )
        self.use_external_action.setChecked(self.external)
        option_menu.addAction(self.use_external_action)
        option_menu.triggered.connect(self.toggle_external)

        self.large_archive_action = QAction(
            "Use Large Archive Architecture?", self, checkable=True
        )
        self.large_archive_action.setToolTip(
            "Change the system to use Large Archives, a slower system that handles large files better"
        )
        self.large_archive_action.setChecked(
            str_to_bool(self.settings.value("settings/large_archive", "0"))
        )
        option_menu.addAction(self.large_archive_action)
        option_menu.triggered.connect(self.toggle_large_archives)

        self.preview_action = QAction("Preview?", self, checkable=True)
        self.preview_action.setToolTip("Enable previewing files")
        self.preview_action.setChecked(str_to_bool(self.settings.value("settings/preview", "1")))
        option_menu.addAction(self.preview_action)
        option_menu.triggered.connect(self.toggle_preview)

        option_menu.addAction("Set encoding", self.set_encoding)

    @property
    def dark_mode(self):
        return str_to_bool(self.settings.value("settings/dark_mode", "1"))

    @dark_mode.setter
    def dark_mode(self, value):
        self.settings.setValue("settings/dark_mode", int(value))
        self.settings.sync()

    @property
    def encoding(self):
        return self.settings.value("settings/encoding", "latin_1")

    @encoding.setter
    def encoding(self, value):
        self.settings.setValue("settings/encoding", value)
        self.settings.sync()

    @property
    def external(self):
        return str_to_bool(self.settings.value("settings/external", "0"))

    @external.setter
    def external(self, value):
        self.settings.setValue("settings/external", int(value))
        self.settings.sync()

    def is_using_large_archive(self):
        return str_to_bool(self.settings.value("settings/large_archive", "0"))

    def is_file_selected(self):
        if not self.listwidget.active_list.selectedItems():
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

        try:
            self.archive.save(path)
            QMessageBox.information(self, "Done", "Archive has been saved")
        except utils.MaxSizeError:
            QMessageBox.warning(
                self,
                "File Size Error",
                "File has reached maximum size, the BIG format only supports up to 4.3GB per archive. Please remove some files and try saving again.",
            )
        except PermissionError:
            QMessageBox.critical(
                self,
                "Failed",
                "Could not save due to missing permissions. Save somewhere this application has access and restart the application as admin.",
            )

        self.path = path
        self.update_archive_name()

    def _open(self, path):
        try:
            if self.is_using_large_archive():
                archive = LargeArchive(path)
            else:
                with open(path, "rb") as f:
                    archive = Archive(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.archive = archive
        self.path = path
        self.update_archive_name()
        self.listwidget.update_list(True)

        try:
            self.archive.save()
        except PermissionError:
            QMessageBox.warning(
                self,
                "Warning",
                "The file you loaded is write-protected. You will not be able to save any changes. Copy this file to another directory and open it or relaunch FinalBIGv2 as admin if you are planning to modify it.",
            )

    def _new(self):
        self.archive = (
            LargeArchive.empty(tempfile.NamedTemporaryFile().name)
            if self.is_using_large_archive()
            else Archive.empty()
        )
        self.path = None
        self.listwidget.update_list(True)
        self.update_archive_name()

    def _remove_file_tab(self, index):
        self.tabs.remove_tab(index)

    def _remove_list_tab(self, index):
        if self.listwidget.currentIndex() == self.listwidget.count() - 2:
            self.listwidget.setCurrentIndex(self.listwidget.count() - 3)

        self.listwidget.remove_tab(index)

    def add_file_list(self, name="List"):
        widget = FileList(self)
        widget.itemSelectionChanged.connect(self.file_single_clicked)
        widget.doubleClicked.connect(self.file_double_clicked)
        widget.update_list()

        self.listwidget.insertTab(self.listwidget.count() - 1, widget, name)
        self.listwidget.setCurrentIndex(self.listwidget.count() - 2)

    def open_new_tab(self):
        if self.listwidget.currentIndex() != self.listwidget.count() - 1:
            self.tab_current_index = self.listwidget.currentIndex()
            return

        name = "List"
        if self.listwidget.count() != 1:
            name, ok = QInputDialog.getText(self, "Tab name", "Pick a name for your new tab:")
            if not ok:
                return self.listwidget.setCurrentIndex(self.tab_current_index)

        self.add_file_list(name)
        self.tab_current_index = self.listwidget.currentIndex()

    def show_help(self):
        string = HELP_STRING.format(
            shortcuts="\n".join(
                f"<li><b>{s[0] if isinstance(s[0], str) else s[0].key().toString()}</b> - {s[1]} </li>"
                for s in self.shorcuts
            )
        )
        QMessageBox.information(self, "Help", string)

    def show_about(self):
        QMessageBox.information(self, "About", ABOUT_STRING.format(version=__version__))

    def set_encoding(self):
        name, ok = QInputDialog.getItem(
            self,
            "Encoding",
            "Select an encoding",
            ENCODING_LIST,
            ENCODING_LIST.index(self.encoding),
            False,
        )
        if not ok:
            return

        self.encoding = name

    def toggle_preview(self):
        self.settings.setValue("settings/preview", int(self.preview_action.isChecked()))
        self.settings.sync()

    def toggle_large_archives(self):
        self.settings.setValue(
            "settings/large_archive", int(self.large_archive_action.isChecked())
        )
        self.settings.sync()
        QMessageBox.information(self, "Large Archive Setting Changed", f"The large archive settings has been {'enabled' if self.large_archive_action.isChecked() else 'disabled'}, please restart FinalBIGv2 to apply the change.")

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

    def toggle_external(self):
        is_checked = self.use_external_action.isChecked()
        self.external = is_checked

    def dump_list(self, filtered):
        file = QFileDialog.getSaveFileName(self, "Save dump")[0]
        if not file:
            return

        if filtered:
            file_list = (
                self.listwidget.active_list.item(x).text()
                for x in range(self.listwidget.active_list.count())
                if not self.listwidget.active_list.item(x).isHidden()
            )
        else:
            file_list = self.archive.file_list()

        with open(file, "w") as f:
            f.write("\n".join(file_list))

        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def merge_archives(self):
        files = QFileDialog.getOpenFileNames(self, "Select an archive to merge", filter="*.big")[0]

        if not files:
            return

        files.reverse()
        files_added = []
        for file in files:
            files_added.extend(self._merge_archives(file))

        self.listwidget.add_files(files_added)

    def _merge_archives(self, path):
        if self.is_using_large_archive():
            archive = LargeArchive(path)
        else:
            with open(path, "rb") as f:
                archive = Archive(f.read())

        skip_all = False
        files_added = []
        files = archive.file_list()
        length = len(files)
        text_box = QMessageBox(
            QMessageBox.Icon.Information,
            "Processing archives",
            f"Processing archive: <b>{path}</b><br>Getting ready to start processing archive. Found {length} files",
            self,
        )
        text_box.setStandardButtons(0)
    
        text_box.show()
        QApplication.processEvents()

        for index, file in enumerate(files):
            text_box.setText(
                f"Processing archive: <b>{path}</b><br>File: ({index+1}/{length})<br>Processing: <b>{file}</b>"
            )
            QApplication.processEvents()
            if self.archive.file_exists(file):
                if not skip_all:
                    ret = QMessageBox.question(
                        self,
                        "Overwrite file?",
                        f"<b>{file}</b> already exists, overwrite?",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No
                        | QMessageBox.StandardButton.YesToAll,
                        QMessageBox.StandardButton.No,
                    )
                    if ret == QMessageBox.StandardButton.No:
                        continue

                    if ret == QMessageBox.StandardButton.YesToAll:
                        skip_all = True

                self.archive.remove_file(file)

            self.archive.add_file(file, archive.read_file(file))

            files_added.append(file)

            size = self.archive.archive_memory_size()
            if size > 524288000:
                print(f"reached {size}, dumping on file {index}")

                try:
                    self.archive.save()
                except utils.MaxSizeError:
                    QMessageBox.warning(
                        self,
                        "File Size Error",
                        "File has reached maximum size, the BIG format only supports up to 4.3GB per archive.",
                    )
                    self.archive.modified_entries = {}
                    break

        text_box.close()

        return files_added

    def search_archive(self, regex):
        search, ok = QInputDialog.getText(
            self,
            "Search archive",
            f"This will search through the currently filtered list. Search keyword{' (Regex)' if regex else ''}:",
        )
        if not ok:
            return

        def update_list_with_matches(returned):
            matches = returned[0]
            for x in range(self.listwidget.active_list.count()):
                item = self.listwidget.active_list.item(x)

                if not item.isHidden():
                    item.setHidden(item.text() not in matches)

            self.message_box.done(1)
            QMessageBox.information(
                self,
                "Search finished",
                f"Found <b>{returned[1]}</b> instances over <b>{len(matches)}</b> files. Filtering list.",
            )

        self.message_box = QMessageBox(
            QMessageBox.Icon.Information,
            "Search in progress",
            "Searching the archive, please wait...",
            QMessageBox.StandardButton.Ok,
            self,
        )
        self.message_box.button(QMessageBox.StandardButton.Ok).setEnabled(False)

        self.thread = ArchiveSearchThread(self, search, self.encoding, self.archive, regex)
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

        self.listwidget.active_list.add_file(file)

    def add_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Add directory")
        if not path:
            return

        self.listwidget.active_list.add_folder(path)

    def new_file(self):
        self.listwidget.active_list.add_file(None, blank=True)

    def filter_list(self):
        search = self.search.currentText()
        invert = self.invert_box.isChecked()
        re_filter = self.re_filter_box.isChecked()

        for x in range(self.listwidget.active_list.count()):
            item = self.listwidget.active_list.item(x)
            if item.isHidden() and re_filter:
                continue

            if search == "":
                item.setHidden(False)
            else:
                hide = not fnmatch.fnmatchcase(item.text(), search)
                if invert:
                    hide = not hide

                item.setHidden(hide)

        if search == "":
            return

        if not any(
            self.search.itemText(x)
            for x in range(self.search.count())
            if self.search.itemText(x) == search
        ):
            self.search.addItem(search)

        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

    def delete(self):
        if not self.is_file_selected():
            return

        deleted = []
        skip_all = False
        for item in self.listwidget.active_list.selectedItems():
            name = item.text()
            if not skip_all:
                ret = QMessageBox.question(
                    self,
                    "Delete file?",
                    f"Are you sure you want to delete <b>{name}</b>?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.YesToAll,
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

        self.listwidget.remove_files([x[0] for x in deleted])
        QMessageBox.information(self, "Done", "File selection has been deleted")

    def clear_preview(self):
        if self.tabs.count() < 0:
            return

        name = self.tabs.tabText(0)
        if is_preview(name):
            self._remove_file_tab(0)

    def copy_name(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.active_list.currentItem().text()
        app.clipboard().setText(original_name)

    def rename(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.active_list.currentItem().text()

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

        self.listwidget.active_list.currentItem().setText(name)
        QMessageBox.information(self, "Done", "File renamed")

    def extract(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.active_list.selectedItems()

        if len(items) > 1:
            path = QFileDialog.getExistingDirectory(self, "Extract filtered files to directory")
            if not path:
                return

            self.archive.extract(path, files=[item.text() for item in items])
        else:
            item = items[0]
            name = item.text()
            file_name = name.split("\\")[-1]
            path = QFileDialog.getSaveFileName(self, "Extract file", file_name)[0]
            if not path:
                return

            with open(path, "wb") as f:
                f.write(self.archive.read_file(name))

        QMessageBox.information(self, "Done", "File selection has been extracted")

    def extract_all(self):
        path = QFileDialog.getExistingDirectory(self, "Extract all files to directory")
        if not path:
            return

        self.archive.extract(path)
        QMessageBox.information(self, "Done", "All files have been extracted")

    def extract_filtered(self):
        path = QFileDialog.getExistingDirectory(self, "Extract filtered files to directory")
        if not path:
            return

        files = [
            self.listwidget.active_list.item(x).text()
            for x in range(self.listwidget.active_list.count())
            if not self.listwidget.active_list.item(x).isHidden()
        ]

        self.archive.extract(path, files=files)
        QMessageBox.information(self, "Done", "Filtered files have been extracted")

    def file_double_clicked(self, _):
        name = self.listwidget.active_list.currentItem().text()

        for x in range(self.tabs.count()):
            if self.tabs.tabText(x) == name:
                self.tabs.setCurrentIndex(x)
                break
        else:
            tab: GenericTab = get_tab_from_file_type(name)(self, self.archive, name)

            if self.external:
                tab.open_externally()
            else:
                tab.generate_layout()

            self.tabs.addTab(tab, name)
            index = self.tabs.count() - 1
            self.tabs.setTabToolTip(index, name)
            self.tabs.setCurrentIndex(index)

            if self.tabs.tabText(0) == preview_name(name):
                self._remove_file_tab(0)

    def file_single_clicked(self):
        if not str_to_bool(self.settings.value("settings/preview", "1")):
            return

        name = self.listwidget.active_list.currentItem().text()
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
                self._remove_file_tab(0)

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

        self._remove_file_tab(index)

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
            self._remove_file_tab(t)

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
