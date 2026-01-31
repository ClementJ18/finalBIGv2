import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List

import platformdirs
import qdarktheme
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from file_views import ListFileView
from utils.utils import ENCODING_LIST, RECENT_FILES_MAX

if TYPE_CHECKING:
    from main import MainWindow
    from tabs.text_tab import TextTab


def str_to_bool(value) -> bool:
    """Convert QSettings string/integer value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class FileView:
    is_favorite: bool
    type: str
    filter: str
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def from_dict(data: dict) -> "FileView":
        return FileView(
            is_favorite=data.get("is_favorite", False),
            type=data.get("type", "list"),
            filter=data.get("filter", ""),
            files=data.get("files", []),
        )


@dataclass
class FileTab:
    file: str
    is_preview: bool
    data: dict = field(default_factory=dict)


@dataclass
class Workplace:
    name: str
    archive_path: str
    notes: str
    version: int
    lists: dict[str, FileView] = field(default_factory=dict)
    tabs: list[FileTab] = field(default_factory=list)
    search: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["lists"] = {k: v.to_dict() for k, v in self.lists.items()}
        data["tabs"] = [asdict(tab) for tab in self.tabs]

        return data

    def from_dict(data: dict) -> "Workplace":
        return Workplace(
            name=data.get("name", ""),
            archive_path=data.get("archive_path", ""),
            lists={k: FileView.from_dict(v) for k, v in data.get("lists", {}).items()},
            tabs=[FileTab(**tab) for tab in data.get("tabs", [])],
            notes=data.get("notes", ""),
            version=data.get("version", 0),
            search=data.get("search", []),
        )


class Settings:
    def __init__(self, main: "MainWindow", org: str = "Necro inc.", app: str = "FinalBIGv2"):
        self._settings = QSettings(org, app)
        self._folder = platformdirs.user_data_dir(app, False, roaming=True)
        self.workspace_folder = os.path.join(self._folder, "workspaces")
        self.workspace_version = 0
        self.main = main
        self.search_archive_regex_bool = False

        if not os.path.exists(self._folder):
            os.makedirs(self._folder)

        if not os.path.exists(self.workspace_folder):
            os.makedirs(self.workspace_folder)

    def get_str(self, key: str, default: str = "") -> str:
        return str(self._settings.value(key, default))

    def set_str(self, key: str, value: str) -> None:
        self.set_value(key, str(value))

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self._settings.value(key, default))

    def set_int(self, key: str, value: int) -> None:
        self.set_value(key, int(value))

    def get_bool(self, key: str, default: bool = False) -> bool:
        return str_to_bool(self._settings.value(key, int(default)))

    def set_bool(self, key: str, value: bool) -> None:
        self.set_value(key, int(value))

    def get_datetime(self, key: str, default: datetime = None) -> datetime:
        value = self._settings.value(key, None)
        if value is None:
            return default
        return datetime.fromisoformat(str(value))

    def set_datetime(self, key: str, value: datetime) -> None:
        self.set_value(key, value.isoformat())

    def set_value(self, key: str, value) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    @property
    def dark_mode(self) -> bool:
        return self.get_bool("settings/dark_mode", True)

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        self.set_bool("settings/dark_mode", value)

    @property
    def encoding(self) -> str:
        return self.get_str("settings/encoding", "latin_1")

    @encoding.setter
    def encoding(self, value: str) -> None:
        self.set_str("settings/encoding", value)

    @property
    def external(self) -> bool:
        return self.get_bool("settings/external", False)

    @external.setter
    def external(self, value: bool) -> None:
        self.set_bool("settings/external", value)

    @property
    def last_dir(self) -> str:
        return self.get_str("settings/last_dir", os.path.expanduser("~"))

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self.set_str("settings/last_dir", value)

    @property
    def large_archive(self) -> bool:
        return self.get_bool("settings/large_archive", False)

    @large_archive.setter
    def large_archive(self, value: bool) -> None:
        self.set_bool("settings/large_archive", value)

    @property
    def preview_enabled(self) -> bool:
        return self.get_bool("settings/preview", True)

    @preview_enabled.setter
    def preview_enabled(self, value: bool) -> None:
        self.set_bool("settings/preview", value)

    @property
    def smart_replace_enabled(self) -> bool:
        return self.get_bool("settings/smart_replace", False)

    @smart_replace_enabled.setter
    def smart_replace_enabled(self, value: bool) -> None:
        self.set_bool("settings/smart_replace", value)

    @property
    def default_file_list_type(self) -> str:
        return self.get_str("settings/default_file_list_type", ListFileView.view_type)

    @default_file_list_type.setter
    def default_file_list_type(self, value: str) -> None:
        self.set_str("settings/default_file_list_type", value)

    @property
    def ignore_version_update(self) -> bool:
        return self.get_str("update/ignore_version_update", None)

    @ignore_version_update.setter
    def ignore_version_update(self, value: str) -> None:
        self.set_str("update/ignore_version_update", value)

    @property
    def update_last_checked(self) -> datetime:
        return self.get_datetime("update/last_checked", None)

    @update_last_checked.setter
    def update_last_checked(self, value: datetime) -> None:
        self.set_datetime("update/last_checked", value)

    def recent_files(self) -> list[str]:
        files = self._settings.value("history/recent_files", [], type=list)
        return [f for f in files if os.path.exists(f)]

    def save_recent_files(self, files: list[str]) -> None:
        self.set_value("history/recent_files", files)

    def add_to_recent_files(self, path):
        path = os.path.normpath(path)
        recent_files = self.recent_files()
        if path in recent_files:
            recent_files.remove(path)
        recent_files.insert(0, path)
        del recent_files[RECENT_FILES_MAX:]
        self.save_recent_files(recent_files)

    def set_encoding(self):
        name, ok = QInputDialog.getItem(
            self.main,
            "Encoding",
            "Select an encoding",
            ENCODING_LIST,
            ENCODING_LIST.index(self.encoding),
            False,
        )
        if not ok:
            return

        self.encoding = name

    def toggle_search_archive_regex(self):
        self.search_archive_regex_bool = not self.search_archive_regex_bool

    def toggle_preview(self):
        self.preview_enabled = self.main.preview_action.isChecked()

    def toggle_large_archives(self):
        is_checked = self.main.large_archive_action.isChecked()
        self.large_archive = is_checked

        message = f"The large archive settings has been {'enabled' if is_checked else 'disabled'}, please restart FinalBIGv2 to apply the change."
        if is_checked:
            message += "\n\nNote: Large archives takes less memory but may increase loading times."
        QMessageBox.information(
            self.main,
            "Large Archive Setting Changed",
            message,
        )

    def toggle_dark_mode(self):
        is_checked = self.main.dark_mode_action.isChecked()
        self.dark_mode = is_checked

        if is_checked:
            qdarktheme.setup_theme("dark", corner_shape="sharp")
        else:
            qdarktheme.setup_theme("light", corner_shape="sharp")

        for x in range(self.main.tabs.count()):
            widget: TextTab = self.main.tabs.widget(x)
            if hasattr(widget, "text_widget"):
                widget.text_widget.toggle_dark_mode(is_checked)

    def toggle_external(self):
        self.external = self.main.use_external_action.isChecked()

    def toggle_smart_replace(self):
        self.smart_replace_enabled = self.main.smart_replace_action.isChecked()

    def set_default_file_list_type(self, view_type: str):
        """Set the default file list view type."""
        self.default_file_list_type = view_type

    def get_workspace_path(self, name: str) -> str:
        return os.path.join(self.workspace_folder, f"{name}.fbigv2")

    def workspace_exists(self, name: str) -> bool:
        workspace_file = self.get_workspace_path(name)
        return os.path.exists(workspace_file)

    def get_workspace(self, name: str) -> Workplace:
        workspace_file = self.get_workspace_path(name)
        if os.path.exists(workspace_file):
            with open(workspace_file, "r") as f:
                return Workplace.from_dict(json.load(f))

        return Workplace(
            name="",
            archive_path="",
            notes="",
            version=self.workspace_version,
            lists={},
            tabs=[],
            search="",
        )

    def save_workspace(self, name: str, data: Workplace) -> None:
        workspace_file = self.get_workspace_path(name)
        data = data.to_dict()
        with open(workspace_file, "w") as f:
            json.dump(data, f, indent=2)

    def list_recent_workspaces(self) -> list[str]:
        workspaces = []
        for file in os.listdir(self.workspace_folder):
            if file.endswith(".fbigv2"):
                path = os.path.join(self.workspace_folder, file)
                mod_time = datetime.fromtimestamp(os.path.getmtime(path))
                workspaces.append((os.path.splitext(file)[0], mod_time))

        workspaces.sort(key=lambda x: x[1], reverse=True)
        return [workspace[0] for workspace in workspaces]

    def list_workspaces(self) -> list[str]:
        workspaces = []
        for file in os.listdir(self.workspace_folder):
            if file.endswith(".fbigv2"):
                workspaces.append(os.path.splitext(file)[0])
        return workspaces

    def delete_workspace(self, name: str) -> None:
        workspace_file = self.get_workspace_path(name)
        if os.path.exists(workspace_file):
            os.remove(workspace_file)

        self.main.update_recent_workspace_menu()

    def rename_workspace(self, old_name: str, new_name: str) -> bool:
        """Rename a workspace. Returns True if successful."""
        old_path = self.get_workspace_path(old_name)
        new_path = self.get_workspace_path(new_name)

        if not os.path.exists(old_path):
            return False
        if os.path.exists(new_path):
            return False

        os.rename(old_path, new_path)
        self.main.update_recent_workspace_menu()
        return True
