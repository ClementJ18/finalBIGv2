import os
import sys
import tempfile
import traceback
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING, cast

import moddb
import qdarktheme
from moddb.errors import ModdbException
from pyBIG import InDiskArchive, InMemoryArchive, base_archive
from PyQt6.QtCore import QEvent, Qt, QTimer
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
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabBar,
)

from file_views import get_file_view_class
from misc import NewTabDialog, WrappingInputDialog
from search import SearchManager
from settings import FileTab, FileView, Settings, Workplace
from tabs import get_tab_from_file_type
from ui import HasUiElements, generate_ui
from utils.utils import (
    ABOUT_STRING,
    HELP_STRING,
    add_to_windows_recent,
    normalize_name,
    preview_name,
    resource_path,
)
from workspaces import WorkspaceDialog

if TYPE_CHECKING:
    from tabs.generic_tab import GenericTab

__version__ = "0.14.0"

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
        self.workspace_name = None

        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.auto_save_workspace)
        self.autosave_timer.setInterval(5 * 60 * 1000)

        self.settings = Settings(self)
        if self.settings.dark_mode:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")

        generate_ui(self)
        self.update_archive_name("No Archive Open")
        self.lock_ui(True)
        self.update_recent_files_menu()

        path_arg = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
        if path_arg:
            if path_arg.endswith(".fbigv2"):
                workspace_name = os.path.splitext(os.path.basename(path_arg))[0]
                workspace = self.settings.get_workspace(workspace_name)
                self.restore_workspace(workspace_name, workspace)
            else:
                self._open(path_arg)

        self.showMaximized()
        QTimer.singleShot(1000, self.post_init)

    def post_init(self):
        self.check_for_updates()

    def check_for_updates(self):
        if self.settings.update_last_checked is not None:
            delta = datetime.now() - self.settings.update_last_checked
            if delta.days < 3:
                return

        self.settings.update_last_checked = datetime.now()

        try:
            r: moddb.File = moddb.parse_page(
                "https://www.moddb.com/games/battle-for-middle-earth-ii/downloads/finalbigv2"
            )
        except ModdbException:
            return

        latest_version = r.name.split("-")[-1].strip()
        if self.settings.ignore_version_update == latest_version:
            return

        if latest_version != __version__:
            msg = QMessageBox(
                QMessageBox.Icon.Information,
                "Update Available",
                f"A new version of FinalBIGv2 is available: {latest_version}\nYou are currently using version: {__version__}\n\nWould you like to visit the download page?",
                parent=self,
            )
            msg.addButton(QPushButton("Yes"), QMessageBox.ButtonRole.YesRole)
            msg.addButton(QPushButton("Ignore this version"), QMessageBox.ButtonRole.NoRole)
            msg.addButton(QPushButton("No"), QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton().text() == "Ignore this version":
                self.settings.ignore_version_update = latest_version
            elif msg.clickedButton().text() == "Yes":
                webbrowser.open(
                    "https://www.moddb.com/games/battle-for-middle-earth-ii/downloads/finalbigv2"
                )

    def manage_workspace(self):
        workspaces = self.settings.list_workspaces()
        if not workspaces:
            QMessageBox.information(
                self,
                "No Workspaces",
                "No workspaces have been saved yet. Please save a workspace first.",
            )
            return

        dialog = WorkspaceDialog(self, workspaces)
        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return

        workspace_name = dialog.textValue()
        workspace = self.settings.get_workspace(workspace_name)
        archive_path = workspace.archive_path
        if not archive_path or not os.path.exists(archive_path):
            ret = QMessageBox.question(
                self,
                "Archive Not Found",
                f"The archive path stored in this workspace does not exist:\n{archive_path}\n\nWould you like to locate it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if ret == QMessageBox.StandardButton.No:
                return

            new_path = QFileDialog.getOpenFileName(
                self, "Locate archive", self.settings.last_dir, "Big files (*.big);;All files (*)"
            )[0]
            if not new_path:
                return

            workspace.archive_path = new_path
            self.settings.save_workspace(workspace_name, workspace)

        if not self.close_unsaved():
            return

        self.restore_workspace(workspace_name, workspace)
        add_to_windows_recent(self.settings.get_workspace_path(workspace_name))

    def open_recent_workspace(self):
        action = self.sender()
        if action:
            workspace_name = action.data()
            workspace = self.settings.get_workspace(workspace_name)
            archive_path = workspace.archive_path
            if not archive_path or not os.path.exists(archive_path):
                ret = QMessageBox.question(
                    self,
                    "Archive Not Found",
                    f"The archive path stored in this workspace does not exist:\n{archive_path}\n\nWould you like to locate it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if ret == QMessageBox.StandardButton.No:
                    return

                new_path = QFileDialog.getOpenFileName(
                    self,
                    "Locate archive",
                    self.settings.last_dir,
                    "Big files (*.big);;All files (*)",
                )[0]
                if not new_path:
                    return

                archive_path = new_path
                workspace.archive_path = new_path
                self.settings.save_workspace(workspace_name, workspace)

            if not self.close_unsaved():
                return

            self.restore_workspace(workspace_name, workspace)
            add_to_windows_recent(self.settings.get_workspace_path(workspace_name))

    def auto_save_workspace(self):
        """Automatically save the current workspace if one is open."""
        if self.workspace_name and self.archive:
            self._save_workspace(self.workspace_name)

    def save_workspace(self):
        workspace_name, ok = QInputDialog.getText(
            self,
            "Save Workspace",
            "Enter a name for the workspace:",
            text=self.workspace_name if self.workspace_name else "MyWorkspace",
        )

        if not ok or not workspace_name:
            return

        if self.settings.workspace_exists(workspace_name):
            ret = QMessageBox.question(
                self,
                "Overwrite Workspace?",
                f"A workspace named <b>{workspace_name}</b> already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.No:
                return

        self._save_workspace(workspace_name)

        self.workspace_name = workspace_name
        self.autosave_timer.start()

        QMessageBox.information(
            self, "Workspace Saved", f"Workspace <b>{workspace_name}</b> has been saved."
        )

    def _save_workspace(self, workspace_name: str):
        existing_workspace = self.settings.get_workspace(workspace_name)
        new_workspace = Workplace(
            name=workspace_name,
            archive_path=self.path,
            version=self.settings.workspace_version,
            notes=existing_workspace.notes if existing_workspace else "",
            lists={},
            tabs=[],
            search=[self.search.itemText(i) for i in range(self.search.count())],
        )

        for i in range(self.listwidget.count() - 1):
            file_list_widget = self.listwidget.widget(i)
            file_list = FileView(
                is_favorite=file_list_widget.is_favorite,
                type=file_list_widget.view_type,
                filter=file_list_widget.filter,
                files=[],
            )

            if file_list_widget.is_favorite:
                file_list.files = [
                    file_list_widget.get_item_path(item) for item in file_list_widget.get_items()
                ]

            new_workspace.lists[self.listwidget.tabText(i)] = file_list

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            new_workspace.tabs.append(
                FileTab(file=tab.name, is_preview=tab.preview, data=tab.to_dict())
            )

        self.settings.save_workspace(workspace_name, new_workspace)
        add_to_windows_recent(self.settings.get_workspace_path(workspace_name))
        self.update_recent_workspace_menu()

    def restore_workspace(self, workspace_name: str, workspace: Workplace):
        version = int(workspace.version)
        if version != self.settings.workspace_version:
            self.migrate_workspace(workspace, version)

        self._open(workspace.archive_path)

        files = self.archive.file_list()
        for list_name, list_data in workspace.lists.items():
            self.add_file_list(list_name, list_data.type)
            file_list_widget = self.listwidget.active_list
            file_list_widget.filter = list_data.filter

            if list_data.is_favorite:
                file_list_widget.is_favorite = True
                self.listwidget.favorite_list = file_list_widget
                file_list_widget.add_files([file for file in list_data.files if file in files])
            else:
                file_list_widget.add_files(files)

            if file_list_widget.filter is not None:
                search, invert, use_regex = file_list_widget.filter
                self.filter_list(file_list_widget, search, invert, use_regex, re_filter=False)

        self.remove_list_tab(0)

        self.search.addItems(workspace.search)

        def update_tab():
            for tab_data in workspace.tabs:
                tab = self._create_tab(tab_data.file, preview=tab_data.is_preview)
                tab.from_dict(tab_data.data)

        QTimer.singleShot(0, update_tab)

        self.workspace_name = workspace_name
        self.autosave_timer.start()
        self.update_archive_name()

    def migrate_workspace(self, data: dict, version: int):
        return data

    def close_workspace(self):
        """Close the current workspace and archive."""
        if self.close_archive():
            self.workspace_name = None
            self.autosave_timer.stop()
            self.update_archive_name("No Archive Open")
            self.update_recent_workspace_menu()

    def close_archive(self):
        if not self.close_unsaved():
            return False

        self.autosave_timer.stop()
        self.workspace_name = None
        self.archive = None
        self.path = None

        for i in reversed(range(self.tabs.count())):
            self.remove_file_tab(i)

        for i in reversed(range(self.listwidget.count() - 1)):
            self.remove_list_tab(i)

        self.update_archive_name("No Archive Open")
        self.lock_ui(True)
        self.update_recent_files_menu()

        return True

    def lock_ui(self, locked: bool):
        """Disable or enable all widgets & actions except the exceptions."""
        for action in cast(list[QAction], self.findChildren(QAction)):
            if action.menu() is not None:
                continue

            if action not in self.lock_exceptions:
                action.setEnabled(not locked)

        self.listwidget.setEnabled(not locked)
        self.tabs.setEnabled(not locked)
        self.search.setEnabled(not locked)

    def add_to_recent_files(self, path):
        self.settings.add_to_recent_files(path)
        self.update_recent_files_menu()
        add_to_windows_recent(path)

    def update_recent_files_menu(self):
        recent_files = self.settings.recent_files()
        self.recent_menu.clear()
        if not recent_files:
            action = self.recent_menu.addAction("No Recent Files")
            action.setEnabled(False)
            return
        for index, path in enumerate(recent_files):
            action = self.recent_menu.addAction(f"&{index + 1}. {path}", self.open_recent_file)
            if path == self.path:
                action.setEnabled(False)

            self.lock_exceptions.append(action)
            action.setData(path)
            action.setToolTip(path)

    def update_recent_workspace_menu(self):
        recent_workspaces = self.settings.list_recent_workspaces()
        actions = self.workspace_menu.actions()
        for action in actions[4:]:
            self.workspace_menu.removeAction(action)

        if not recent_workspaces:
            action = self.workspace_menu.addAction("No Workspaces")
            action.setEnabled(False)
            return
        for index, workspace_name in enumerate(recent_workspaces):
            action = self.workspace_menu.addAction(
                f"&{index + 1}. {workspace_name}", self.open_recent_workspace
            )
            if workspace_name == self.workspace_name:
                action.setEnabled(False)

            self.lock_exceptions.append(action)
            action.setData(workspace_name)
            action.setToolTip(workspace_name)

    def open_recent_file(self):
        action = self.sender()
        if action:
            path = action.data()
            try:
                success = self._open(path)
            except FileNotFoundError:
                success = False

        if not success:
            recent_files = self.settings.recent_files()
            if path in recent_files:
                recent_files.remove(path)
                self.settings.save_recent_files(recent_files)

    def update_archive_name(self, name=None):
        if name is None:
            name = self.path or "Untitled Archive"

        title = f"{os.path.basename(name)} - {self.base_name}"
        if self.workspace_name:
            title = f"{os.path.basename(name)} [{self.workspace_name}] - {self.base_name}"

        self.setWindowTitle(title)

    def _save(self, path):
        if path is None:
            path = QFileDialog.getSaveFileName(
                self, "Save archive", self.settings.last_dir, "Big files (*.big);;All files (*)"
            )[0]

        if not path:
            return False

        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab.unsaved:
                tab.save()

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

        self.add_file_list()
        self.tab_current_index = self.listwidget.currentIndex()
        self.listwidget.update_list(True)
        self.lock_ui(False)

        return True

    def _new(self):
        formats_map = {
            "BIG4 (for BFME games)": "BIG4",
            "BIGF (for C&C Generals)": "BIGF",
        }

        item, ok = QInputDialog.getItem(
            self, "New Archive", "Select archive format:", list(formats_map.keys()), 0, False
        )

        if not ok:
            return

        if not self.close_unsaved():
            return

        self.close_archive()
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

    def add_file_list(self, name="List", widget_type=None):
        if widget_type is None:
            widget_type = self.settings.default_file_list_type

        widget = get_file_view_class(widget_type)(self)
        widget.update_list()

        self.listwidget.insertTab(self.listwidget.count() - 1, widget, name)
        self.listwidget.setCurrentIndex(self.listwidget.count() - 2)

    def open_new_tab(self):
        if self.listwidget.currentIndex() != self.listwidget.count() - 1:
            self.tab_current_index = self.listwidget.currentIndex()
            return

        if self.archive is None:
            self.tab_current_index = self.listwidget.currentIndex()
            return

        existing_names = {self.listwidget.tabText(i) for i in range(self.listwidget.count() - 1)}
        counter = 1
        while f"List {counter}" in existing_names:
            counter += 1

        dialog = NewTabDialog(self, f"List {counter}")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return self.listwidget.setCurrentIndex(self.tab_current_index)

        name, widget_type = dialog.get_values()
        if not name:
            return self.listwidget.setCurrentIndex(self.tab_current_index)

        self.add_file_list(name, widget_type)
        self.tab_current_index = self.listwidget.currentIndex()

    def show_help(self):
        QMessageBox.information(self, "Help", HELP_STRING)

    def show_about(self):
        QMessageBox.information(self, "About", ABOUT_STRING.format(version=__version__))

    def dump_list(self, filtered):
        file = QFileDialog.getSaveFileName(self, "Save dump", self.settings.last_dir)[0]
        if not file:
            return

        if filtered:
            active_list = self.listwidget.active_list
            file_list = (
                active_list.get_item_path(item)
                for item in active_list.get_items()
                if not item.isHidden()
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
        self._new()

    def open(self):
        file = QFileDialog.getOpenFileName(
            self, "Open file", self.settings.last_dir, "Big files (*.big);;All files (*)"
        )[0]
        if not file:
            return

        if not self.close_unsaved():
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

    def save_all_editors(self):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).save()

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
        if self.settings.smart_replace_enabled:
            files = self.archive.file_list()
            name_components = name.split("\\")
            complete_component = name_components.pop()
            for component in reversed(name_components):
                filtered_files = [f for f in files if f.endswith(complete_component)]
                if not filtered_files:
                    break

                name = filtered_files[0]
                if len(filtered_files) == 1:
                    break

                files = filtered_files
                complete_component = f"{component}\\{complete_component}"

        if ask_name:
            name, ok = WrappingInputDialog.getText(
                self,
                "Filename",
                "Save the file under the following name:",
                name,
            )
            if not ok or not name:
                return False

        ret = self.add_file_to_archive(url, name, blank, skip_all=not ask_name)
        if ret != QMessageBox.StandardButton.No:
            self.listwidget.add_files([name])
            self.refresh_tabs([name])

        return ret

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

    def is_file_selected(self):
        if not self.listwidget.active_list.is_file_selected():
            QMessageBox.warning(self, "No file selected", "You have not selected a file")
            return False

        return True

    def get_selected_files(self) -> list[str]:
        return self.listwidget.active_list.get_selected_files()

    def delete(self):
        if not self.is_file_selected():
            return

        deleted = []
        skip_all = False
        for name in self.get_selected_files():
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

            deleted.append(name)
            self.archive.remove_file(name)

        if not deleted:
            return

        for i in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(i)
            if tab.name in deleted:
                self.tabs.remove_tab(i)

        self.listwidget.remove_files(deleted)
        QMessageBox.information(self, "Done", "File selection has been deleted")

    def clear_preview(self):
        if self.tabs.count() < 0:
            return

        tab = self.tabs.widget(0)
        if tab.preview:
            self.remove_file_tab(0)

    def copy_name(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.active_list.current_item_text()
        app.clipboard().setText(original_name)

    def rename(self):
        if not self.is_file_selected():
            return

        original_name = self.listwidget.active_list.current_item_text()

        name, ok = WrappingInputDialog.getText(
            self, "Filename", f"Rename {original_name} as:", original_name
        )
        if not ok:
            return

        if name == original_name:
            return

        for i in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(i)
            if tab.name == name:
                self.tabs.remove_tab(i)

        self.archive.add_file(name, self.archive.read_file(original_name))
        self.archive.remove_file(original_name)

        self.listwidget.remove_files([original_name])
        self.listwidget.add_files([name])

        QMessageBox.information(self, "Done", "File renamed")

    def add_favorites(self):
        if not self.is_file_selected():
            return

        self.listwidget.add_favorites(self.get_selected_files())

    def remove_favorites(self):
        if not self.is_file_selected():
            return

        self.listwidget.remove_favorites(self.get_selected_files())

    def extract(self):
        if not self.is_file_selected():
            return

        files = self.get_selected_files()
        if len(files) > 1:
            path = QFileDialog.getExistingDirectory(
                self, "Extract filtered files to directory", self.settings.last_dir
            )
            if not path:
                return

            self.settings.last_dir = path
            self.archive.extract(path, files=files)
        else:
            name = files[0]
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
            active_list.get_item_path(item)
            for item in active_list.get_items()
            if not item.isHidden()
        ]

        self.archive.extract(path, files=files)
        self.settings.last_dir = path
        QMessageBox.information(self, "Done", "Filtered files have been extracted")

    def open_externally(self):
        name = self.listwidget.active_list.current_item_text()
        tab = get_tab_from_file_type(name)(self, self.archive, name, False)
        tab.open_externally()

    def _find_tab_index(self, name: str, preview: bool):
        for x in range(self.tabs.count()):
            tab = self.tabs.widget(x)
            if tab.name == name and (tab.preview == preview or preview is None):
                return x

        return -1

    def _create_tab(self, name: str, preview: bool = False) -> "GenericTab":
        first_tab = self.tabs.widget(0)

        if preview:
            if first_tab and first_tab.name == name:
                self.tabs.setCurrentIndex(0)
                return first_tab

            tab = get_tab_from_file_type(name)(self, self.archive, name, preview)
            tab.generate_preview()
            if first_tab and first_tab.preview and self.tabs.currentIndex() >= 0:
                self.remove_file_tab(0)

            self.tabs.insertTab(0, tab, preview_name(name))
            self.tabs.setTabToolTip(0, preview_name(name))
            self.tabs.setCurrentIndex(0)
            return tab

        for i in range(self.tabs.count()):
            existing_tab = self.tabs.widget(i)
            if existing_tab.name == name and not existing_tab.preview:
                self.tabs.setCurrentIndex(i)
                return existing_tab

        if first_tab and first_tab.preview and first_tab.name == name:
            self.remove_file_tab(0)

        tab = get_tab_from_file_type(name)(self, self.archive, name, preview)
        if self.settings.external:
            tab.open_externally()
        else:
            tab.generate_layout()

        self.tabs.addTab(tab, name)
        index = self.tabs.count() - 1
        self.tabs.setTabToolTip(index, name)
        self.tabs.setCurrentIndex(index)

        return tab

    def file_double_clicked(self, _):
        if not self.listwidget.active_list.is_valid_selection():
            return

        name = self.listwidget.active_list.current_item_text()
        idx = self._find_tab_index(name, preview=False)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
        else:
            self._create_tab(name, preview=False)

    def file_single_clicked(self):
        if not self.settings.preview_enabled:
            return

        if not self.listwidget.active_list.is_valid_selection():
            return

        name = self.listwidget.active_list.current_item_text()
        idx = self._find_tab_index(name, preview=None)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
        else:
            self._create_tab(name, preview=True)

    def refresh_tabs(self, files: list[str]):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.name in files:
                self.remove_file_tab(i)
                self._create_tab(tab.name, preview=tab.preview)

    def close_tab_shortcut(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        self.close_tab(index)

    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if tab.unsaved:
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
                tab.save()

        self.remove_file_tab(index)

    def close_unsaved(self):
        if not self.archive:
            return True

        unsaved_tabs = any(self.tabs.widget(i).unsaved for i in range(self.tabs.count()))
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
            yes_to_all = False
            for url in md.urls():
                local_file = url.toLocalFile()
                if local_file.endswith(".big"):
                    self._open(local_file)
                    break

                if os.path.isfile(local_file):
                    ret = self._add_file(local_file, ask_name=not yes_to_all)
                else:
                    ret = self._add_folder(local_file)

                if ret == QMessageBox.StandardButton.YesToAll:
                    yes_to_all = True

            event.acceptProposedAction()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()

    ico_path = resource_path("icon.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))

    w.show()
    sys.exit(app.exec())
