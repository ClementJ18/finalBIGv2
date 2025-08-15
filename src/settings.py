import os
from typing import TYPE_CHECKING
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QInputDialog, QMessageBox
import qdarktheme

from tabs import TextTab
from utils import ENCODING_LIST, RECENT_FILES_MAX

if TYPE_CHECKING:
    from main import MainWindow


def str_to_bool(value) -> bool:
    """Convert QSettings string/integer value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self, main: "MainWindow", org: str = "Necro inc.", app: str = "FinalBIGv2"):
        self._settings = QSettings(org, app)
        self.main = main
        self.search_archive_regex_bool = False

    def get_str(self, key: str, default: str = "") -> str:
        return str(self._settings.value(key, default))

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self._settings.value(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        return str_to_bool(self._settings.value(key, int(default)))

    def set_value(self, key: str, value) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    @property
    def dark_mode(self) -> bool:
        return self.get_bool("settings/dark_mode", True)

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        self.set_value("settings/dark_mode", int(value))

    @property
    def encoding(self) -> str:
        return self.get_str("settings/encoding", "latin_1")

    @encoding.setter
    def encoding(self, value: str) -> None:
        self.set_value("settings/encoding", value)

    @property
    def external(self) -> bool:
        return self.get_bool("settings/external", False)

    @external.setter
    def external(self, value: bool) -> None:
        self.set_value("settings/external", int(value))

    @property
    def last_dir(self) -> str:
        return self.get_str("settings/last_dir", os.path.expanduser("~"))

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self.set_value("settings/last_dir", value)

    @property
    def large_archive(self) -> bool:
        return self.get_bool("settings/large_archive", False)

    @large_archive.setter
    def large_archive(self, value: bool) -> None:
        self.set_value("settings/large_archive", int(value))

    @property
    def preview_enabled(self) -> bool:
        return self.get_bool("settings/preview", True)

    @preview_enabled.setter
    def preview_enabled(self, value: bool) -> None:
        self.set_value("settings/preview", int(value))

    def recent_files(self) -> list[str]:
        files = self._settings.value("history/recent_files", [], type=list)
        return [f for f in files if os.path.exists(f)]

    def save_recent_files(self, files: list[str]) -> None:
        self.set_value("history/recent_files", files)

    def add_to_recent_files(self, path):
        recent_files = self.recent_files()
        if path in recent_files:
            recent_files.remove(path)
        recent_files.insert(0, path)
        del recent_files[RECENT_FILES_MAX:]
        self.save_recent_files(recent_files)

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

    def toggle_search_archive_regex(self):
        self.search_archive_regex_bool = not self.search_archive_regex_bool

    def toggle_preview(self):
        self.preview_enabled = self.main.preview_action.isChecked()

    def toggle_large_archives(self):
        is_checked = self.main.large_archive_action.isChecked()
        self.large_archive = is_checked
        QMessageBox.information(
            self.main,
            "Large Archive Setting Changed",
            f"The large archive settings has been {'enabled' if is_checked else 'disabled'}, please restart FinalBIGv2 to apply the change.",
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
