import os
import sys
import tempfile
import traceback
from typing import cast

import qdarktheme
from pyBIG import InDiskArchive, InMemoryArchive, base_archive
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTabBar,
    QWidget,
)

from misc import FileList
from search import SearchManager
from settings import Settings
from tabs import get_tab_from_file_type
from ui import HasUiElements, generate_ui
from utils import (
    ABOUT_STRING,
    HELP_STRING,
    is_preview,
    is_unsaved,
    normalize_name,
    preview_name,
    resource_path,
)

__version__ = "0.12.0"

basedir = os.path.dirname(__file__)


def handle_exception(exc_type, exc_value, exc_traceback):
    tb = "\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)

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


class MainWindow(QMainWindow, HasUiElements, SearchManager):
    def __init__(self):
        super().__init__()
        self.base_name = "FinalBIG v2"
        self.lock_exceptions = []

        self.tab_current_index = 0

        self.archive = None
        self.path = None

        self.settings = Settings(self)
        if self.settings.dark_mode:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")

        generate_ui(self, basedir)

        self.add_file_list()
        self.close_archive()

        path_arg = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
        if path_arg:
            self._open(path_arg)

        self.showMaximized()

    def close_archive(self):
        if not self.close_unsaved():
            return False

        self.archive = None
        self.path = None

        for i in reversed(range(self.tabs.count())):
            self.remove_file_tab(i)

        if hasattr(self, "listwidget"):
            self.listwidget.update_list(True)

        self.update_archive_name("No Archive Open")
        self.lock_ui(True)
        self.update_recent_files_menu()

        return True

    def lock_ui(self, locked: bool):
        """Disable or enable all widgets & actions except the exceptions."""
        # Lock all actions
        for action in cast(list[QAction], self.findChildren(QAction)):
            if action.menu() is not None:
                continue

            if action not in self.lock_exceptions:
                action.setEnabled(not locked)

        # Lock all widgets (including central widget)
        for widget in cast(list[QWidget], self.findChildren(QWidget)):
            if isinstance(widget, (QMenuBar, QMenu)):
                continue

            widget.setEnabled(not locked)

    def add_to_recent_files(self, path):
        self.settings.add_to_recent_files(path)
        self.update_recent_files_menu()

    def update_recent_files_menu(self):
        recent_files = self.settings.recent_files()
        self.recent_menu.clear()
        if not recent_files:
            action = self.recent_menu.addAction("No Recent Files")
            action.setEnabled(False)
            return
        for path in recent_files:
            action = self.recent_menu.addAction(path, self.open_recent_file)
            if path == self.path:
                action.setEnabled(False)

            self.lock_exceptions.append(action)
            action.setData(path)
            action.setToolTip(path)

    def open_recent_file(self):
        action = self.sender()
        if action:
            path = action.data()
            try:
                success = self._open(path)
            except Exception:
                success = False

        if not success:
            recent_files = self.settings.recent_files()
            if path in recent_files:
                recent_files.remove(path)
                self.settings.save_recent_files(recent_files)

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
            path = QFileDialog.getSaveFileName(
                self, "Save archive", self.settings.last_dir, "Big files (*.big);;All files (*)"
            )[0]

        if not path:
            return False

        for index in range(self.tabs.count()):
            if is_unsaved(self.tabs.tabText(index)):
                self.tabs.widget(index).save()

        try:
            self.archive.save(path)
            QMessageBox.information(self, "Done", "Archive has been saved")
        except base_archive.MaxSizeError:
            QMessageBox.warning(
                self,
                "File Size Error",
                "File has reached maximum size, the BIG format only supports up to 4.3GB per archive. Please remove some files and try saving again.",
            )
            return False
        except PermissionError:
            QMessageBox.critical(
                self,
                "Failed",
                "Could not save due to missing permissions. Save somewhere this application has access and restart the application as admin.",
            )
            return False

        self.path = path
        self.settings.last_dir = os.path.dirname(path)
        self.update_archive_name()
        self.add_to_recent_files(path)
        return True

    def _open(self, path):
        self.close_archive()

        try:
            if self.settings.large_archive:
                archive = InDiskArchive(path)
            else:
                with open(path, "rb") as f:
                    archive = InMemoryArchive(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.archive = archive
        self.path = path
        self.update_archive_name()
        self.add_to_recent_files(path)
        self.listwidget.update_list(True)
        self.lock_ui(False)

        return True

    def _new(self):
        if not self.close_archive():
            return

        formats_map = {
            "BIG4 (for BFME games)": "BIG4",
            "BIGF (for C&C Generals)": "BIGF",
        }

        item, ok = QInputDialog.getItem(
            self, "New Archive", "Select archive format:", list(formats_map.keys()), 0, False
        )
        if not ok:
            self.close_archive()
            return

        header = formats_map[item]
        if self.settings.large_archive:
            temp_path = tempfile.NamedTemporaryFile(delete=False).name
            self.archive = InDiskArchive.empty(header, file_path=temp_path)
        else:
            self.archive = InMemoryArchive.empty(header)

        self.path = None
        self.update_archive_name()
        self.listwidget.update_list(True)
        self.lock_ui(False)

    def remove_file_tab(self, index):
        self.tabs.remove_tab(index)

    def remove_list_tab(self, index):
        if self.listwidget.currentIndex() == self.listwidget.count() - 2:
            self.listwidget.setCurrentIndex(self.listwidget.count() - 3)

        if self.listwidget.widget(index).is_favorite:
            self.listwidget.favorite_list = None

        self.listwidget.remove_tab(index)

    def add_file_list(self, name="List"):
        widget = FileList(self)
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
                for s in self.shortcuts
            )
        )
        QMessageBox.information(self, "Help", string)

    def show_about(self):
        QMessageBox.information(self, "About", ABOUT_STRING.format(version=__version__))

    def dump_list(self, filtered):
        file = QFileDialog.getSaveFileName(self, "Save dump", self.settings.last_dir)[0]
        if not file:
            return

        if filtered:
            active_list = self.listwidget.active_list
            file_list = (
                active_list.item(x).text()
                for x in range(active_list.count())
                if not active_list.item(x).isHidden()
            )
        else:
            file_list = self.archive.file_list()

        with open(file, "w") as f:
            f.write("\n".join(file_list))

        self.settings.last_dir = os.path.dirname(file)
        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def merge_archives(self):
        files = QFileDialog.getOpenFileNames(
            self,
            "Select an archive to merge",
            self.settings.last_dir,
            filter="Big files (*.big);;All files (*)",
        )[0]

        if not files:
            return

        files.reverse()
        files_added = []
        for file in files:
            files_added.extend(self._merge_archives(file))

        self.settings.last_dir = os.path.dirname(files[0])
        self.listwidget.add_files(files_added)

    def _merge_archives(self, path):
        if self.settings.large_archive:
            archive = InDiskArchive(path)
        else:
            with open(path, "rb") as f:
                archive = InMemoryArchive(f.read())

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
                f"Processing archive: <b>{path}</b><br>File: ({index + 1}/{length})<br>Processing: <b>{file}</b>"
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
                    self.archive.save(self.path)
                except base_archive.MaxSizeError:
                    QMessageBox.warning(
                        self,
                        "File Size Error",
                        "File has reached maximum size, the BIG format only supports up to 4.3GB per archive.",
                    )
                    self.archive.modified_entries = {}
                    break

        text_box.close()

        return files_added

    def new(self):
        if not self.close_unsaved():
            return

        self._new()

    def open(self):
        if not self.close_unsaved():
            return

        file = QFileDialog.getOpenFileName(
            self, "Open file", self.settings.last_dir, "Big files (*.big);;All files (*)"
        )[0]
        if not file:
            return

        self.settings.last_dir = os.path.dirname(file)
        self._open(file)

    def save(self):
        return self._save(self.path)

    def save_as(self):
        self._save(None)

    def save_editor(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        self.tabs.widget(index).save()

    def add_file(self):
        file = QFileDialog.getOpenFileName(self, "Add file", self.settings.last_dir)[0]
        if not file:
            return

        self.settings.last_dir = os.path.dirname(file)
        self._add_file(file)

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Add directory", self.settings.last_dir)
        if not path:
            return

        self.settings.last_dir = path
        self._add_folder(path)

    def new_file(self):
        self._add_file(None, blank=True)

    def _add_file(self, url, *, blank=False, ask_name=True):
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

        ret = self.add_file_to_archive(url, name, blank)
        if ret != QMessageBox.StandardButton.No:
            self.listwidget.add_files([name])

    def _add_folder(self, url):
        skip_all = False
        common_dir = os.path.dirname(url)
        files_to_add = []
        for root, _, files in os.walk(url):
            for f in files:
                full_path = os.path.join(root, f)
                name = normalize_name(os.path.relpath(full_path, common_dir))
                ret = self.add_file_to_archive(full_path, name, blank=False, skip_all=skip_all)

                if ret != QMessageBox.StandardButton.No:
                    files_to_add.append(name)

                if ret == QMessageBox.StandardButton.YesToAll:
                    skip_all = True

        self.listwidget.add_files(files_to_add)

    def add_file_to_archive(self, url, name, blank=False, skip_all=False):
        ret = None
        if self.archive.file_exists(name):
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

            self.archive.remove_file(name)

        try:
            if blank:
                self.archive.add_file(name, b"")
            else:
                with open(url, "rb") as f:
                    self.archive.add_file(name, f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return ret

        return ret

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
            self.remove_file_tab(0)

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

        self.listwidget.remove_files([original_name])
        self.listwidget.add_files([name])

        QMessageBox.information(self, "Done", "File renamed")

    def add_favorites(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.active_list.selectedItems()
        self.listwidget.add_favorites([item.text() for item in items])

    def remove_favorites(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.favorite_list.selectedItems()
        self.listwidget.remove_favorites([item.text() for item in items])

    def extract(self):
        if not self.is_file_selected():
            return

        items = self.listwidget.active_list.selectedItems()

        if len(items) > 1:
            path = QFileDialog.getExistingDirectory(
                self, "Extract filtered files to directory", self.settings.last_dir
            )
            if not path:
                return

            self.settings.last_dir = path
            self.archive.extract(path, files=[item.text() for item in items])
        else:
            item = items[0]
            name = item.text()
            file_name = name.split("\\")[-1]
            path = QFileDialog.getSaveFileName(
                self, "Extract file", os.path.join(self.settings.last_dir, file_name)
            )[0]
            if not path:
                return

            with open(path, "wb") as f:
                f.write(self.archive.read_file(name))

            self.settings.last_dir = os.path.dirname(path)

        QMessageBox.information(self, "Done", "File selection has been extracted")

    def extract_all(self):
        path = QFileDialog.getExistingDirectory(
            self, "Extract all files to directory", self.settings.last_dir
        )
        if not path:
            return

        self.archive.extract(path)
        self.settings.last_dir = path
        QMessageBox.information(self, "Done", "All files have been extracted")

    def extract_filtered(self):
        path = QFileDialog.getExistingDirectory(
            self, "Extract filtered files to directory", self.settings.last_dir
        )
        if not path:
            return

        active_list = self.listwidget.active_list
        files = [
            active_list.item(x).text()
            for x in range(active_list.count())
            if not active_list.item(x).isHidden()
        ]

        self.archive.extract(path, files=files)
        self.settings.last_dir = path
        QMessageBox.information(self, "Done", "Filtered files have been extracted")

    def _find_tab_index(self, name: str):
        for x in range(self.tabs.count()):
            if self.tabs.tabText(x) == name:
                return x

        return -1

    def _create_tab(self, name: str, preview: bool = False):
        if preview:
            if self.tabs.count() > 0 and self.tabs.tabText(0) == preview_name(name):
                self.tabs.setCurrentIndex(0)
                return

            tab = get_tab_from_file_type(name)(self, self.archive, name, preview)
            tab.generate_preview()
            if is_preview(self.tabs.tabText(0)) and self.tabs.currentIndex() >= 0:
                self.remove_file_tab(0)

            self.tabs.insertTab(0, tab, preview_name(name))
            self.tabs.setTabToolTip(0, preview_name(name))
            self.tabs.setCurrentIndex(0)
            return
        else:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == name:
                    self.tabs.setCurrentIndex(i)
                    return

            tab = get_tab_from_file_type(name)(self, self.archive, name, preview)
            if self.settings.external:
                tab.open_externally()
            else:
                tab.generate_layout()

            self.tabs.addTab(tab, name)
            index = self.tabs.count() - 1
            self.tabs.setTabToolTip(index, name)
            self.tabs.setCurrentIndex(index)
            if self.tabs.tabText(0) == preview_name(name):
                self.remove_file_tab(0)

    def file_double_clicked(self, _):
        name = self.listwidget.active_list.currentItem().text()
        idx = self._find_tab_index(name)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
        else:
            self._create_tab(name, preview=False)

    def file_single_clicked(self):
        if not self.settings.preview_enabled:
            return

        name = self.listwidget.active_list.currentItem().text()
        idx = self._find_tab_index(name)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
        else:
            self._create_tab(name, preview=True)

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
                "There is unsaved work, do you want to save before closing?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Cancel:
                return

            if ret == QMessageBox.StandardButton.Yes:
                self.tabs.widget(index).save()

        self.remove_file_tab(index)

    def close_unsaved(self):
        if not self.archive:
            return True

        unsaved_tabs = any(is_unsaved(self.tabs.tabText(i)) for i in range(self.tabs.count()))
        if self.archive.modified_entries or unsaved_tabs:
            ret = QMessageBox.question(
                self,
                "Close unsaved?",
                "There is unsaved work, would you like to save it before closing?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Cancel:
                return False

            if ret == QMessageBox.StandardButton.Yes:
                if not self.save():
                    return False

        for t in range(self.tabs.count()):
            self.remove_file_tab(t)

        return True

    def eventFilter(self, obj: QTabBar, event: QEvent):
        if (
            obj is self.tabs.tabBar()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.MiddleButton
        ):
            index = obj.tabAt(event.pos())
            if index != -1:
                self.close_tab(index)
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event: QCloseEvent):
        if self.close_unsaved():
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                local_file = url.toLocalFile()
                if local_file.endswith(".big"):
                    return self._open(local_file)

                if os.path.isfile(local_file):
                    self._add_file(local_file)
                else:
                    self._add_folder(local_file)

            event.acceptProposedAction()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()

    ico_path = resource_path("icon.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))

    w.show()
    sys.exit(app.exec())
