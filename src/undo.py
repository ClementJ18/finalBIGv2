from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MainWindow


class ArchiveCommand:
    @property
    def description(self) -> str:
        return "Unknown"

    def undo(self, main: MainWindow) -> None:
        raise NotImplementedError

    def redo(self, main: MainWindow) -> None:
        raise NotImplementedError


class AddFileCommand(ArchiveCommand):
    def __init__(self, name: str, data: bytes, replaced_data: bytes | None = None):
        self.name = name
        self.data = data
        self.replaced_data = replaced_data

    @property
    def description(self) -> str:
        return f"Add '{self.name}'"

    def undo(self, main: MainWindow) -> None:
        main.archive.remove_file(self.name)
        if self.replaced_data is not None:
            main.archive.add_file(self.name, self.replaced_data)
        else:
            main.listwidget.remove_files([self.name])

        for i in reversed(range(main.tabs.count())):
            if main.tabs.widget(i).name == self.name:
                main.tabs.remove_tab(i)

    def redo(self, main: MainWindow) -> None:
        if main.archive.file_exists(self.name):
            main.archive.remove_file(self.name)
        else:
            main.listwidget.add_files([self.name])

        main.archive.add_file(self.name, self.data)
        main.refresh_tabs([self.name])


class DeleteFilesCommand(ArchiveCommand):
    def __init__(self, files_data: list[tuple[str, bytes]]):
        self.files_data = files_data

    @property
    def description(self) -> str:
        if len(self.files_data) == 1:
            return f"Delete '{self.files_data[0][0]}'"
        return f"Delete {len(self.files_data)} files"

    def undo(self, main: MainWindow) -> None:
        names = []
        for name, data in self.files_data:
            main.archive.add_file(name, data)
            names.append(name)
        main.listwidget.add_files(names)

    def redo(self, main: MainWindow) -> None:
        names = [name for name, _ in self.files_data]
        for name in names:
            main.archive.remove_file(name)

        for i in reversed(range(main.tabs.count())):
            if main.tabs.widget(i).name in names:
                main.tabs.remove_tab(i)

        main.listwidget.remove_files(names)


class RenameFileCommand(ArchiveCommand):
    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name

    @property
    def description(self) -> str:
        return f"Rename '{self.old_name}'"

    def undo(self, main: MainWindow) -> None:
        data = main.archive.read_file(self.new_name)
        for i in reversed(range(main.tabs.count())):
            if main.tabs.widget(i).name == self.new_name:
                main.tabs.remove_tab(i)
        main.archive.add_file(self.old_name, data)
        main.archive.remove_file(self.new_name)
        main.listwidget.remove_files([self.new_name])
        main.listwidget.add_files([self.old_name])

    def redo(self, main: MainWindow) -> None:
        data = main.archive.read_file(self.old_name)
        for i in reversed(range(main.tabs.count())):
            if main.tabs.widget(i).name == self.old_name:
                main.tabs.remove_tab(i)
        main.archive.add_file(self.new_name, data)
        main.archive.remove_file(self.old_name)
        main.listwidget.remove_files([self.old_name])
        main.listwidget.add_files([self.new_name])


class UndoStack:
    DEFAULT_SIZE = 50

    def __init__(self, max_size: int = DEFAULT_SIZE):
        self.max_size = max_size
        self._undo: list[ArchiveCommand] = []
        self._redo: list[ArchiveCommand] = []

    def resize(self, new_size: int) -> None:
        self.max_size = new_size
        del self._undo[: max(0, len(self._undo) - new_size)]
        del self._redo[: max(0, len(self._redo) - new_size)]

    def push(self, command: ArchiveCommand) -> None:
        self._undo.append(command)
        if len(self._undo) > self.max_size:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, main: MainWindow) -> str | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        command.undo(main)
        self._redo.append(command)
        return command.description

    def redo(self, main: MainWindow) -> str | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        command.redo(main)
        self._undo.append(command)
        return command.description

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_description(self) -> str:
        return self._undo[-1].description if self._undo else ""

    @property
    def redo_description(self) -> str:
        return self._redo[-1].description if self._redo else ""
