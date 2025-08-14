import os
from PyQt6.QtCore import QSettings

from utils import RECENT_FILES_MAX


def str_to_bool(value) -> bool:
    """Convert QSettings string/integer value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self, org: str = "Necro inc.", app: str = "FinalBIGv2"):
        self._settings = QSettings(org, app)

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
