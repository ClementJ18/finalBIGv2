import os
import shutil
import tempfile
from typing import TYPE_CHECKING

from pyBIG.base_archive import BaseArchive
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QWidget
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.utils import human_readable_size, unsaved_name

if TYPE_CHECKING:
    from main import MainWindow


class SaveEventHandler(FileSystemEventHandler):
    def __init__(self, tab, name, tmp_name):
        super().__init__()

        self.tab: GenericTab = tab
        self.file_name = name
        self.tmp_name = tmp_name

    def on_modified(self, event):
        if event.src_path == self.tmp_name:
            QTimer.singleShot(0, self.tab.save)

    def on_moved(self, event):
        if event.dest_path == self.tmp_name:
            QTimer.singleShot(0, self.tab.save)

    # some editors trigger on close when saving so don't use it
    # def on_closed(self, event):
    #     pass


class GenericTab(QWidget):
    def __init__(self, main: "MainWindow", archive: BaseArchive, name: str, preview: bool):
        super().__init__(main)

        self.archive = archive
        self.main = main

        self.name = name
        self.file_type: str = os.path.splitext(name)[1].lower()
        self.data: bytes = self.archive.read_file(name)

        self.external: bool = False
        self.path: str = None

        self.observer = None
        self.tmp = None

        self.preview = preview
        self.unsaved = False

    def generate_layout(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(f"{self.file_type} is not currently supported")

        layout.addWidget(data)

        self.setLayout(layout)

    def generate_preview(self):
        self.generate_layout()

    def become_unsaved(self):
        if self.unsaved:
            return

        self.unsaved = True
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), unsaved_name(self.name))

    def save(self):
        if not self.unsaved:
            return

        self.unsaved = False
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), self.name)

    def search(self):
        pass

    def gather_files(self) -> list:
        return [self.name]

    def open_externally(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText("File opened externally")

        layout.addWidget(data)
        self.setLayout(layout)

        self.tmp = tempfile.TemporaryDirectory(prefix=f"{self.file_type[:1]}-")

        for file in self.gather_files():
            if self.archive.file_exists(file):
                with open(os.path.join(self.tmp.name, os.path.basename(file)), "wb") as f:
                    f.write(self.archive.read_file(file))

        self.path = os.path.join(self.tmp.name, os.path.basename(self.name))
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

        self.observer = Observer()
        self.observer.schedule(SaveEventHandler(self, self.name, self.path), self.tmp.name)

        self.observer.start()
        self.external = True

    def generate_controller(self):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel(f"<b>Size:</b> {human_readable_size(len(self.data))}"))
        controls_layout.addWidget(QLabel(f"<b>Type:</b> {self.file_type}"))

        if not self.preview:
            save_btn = QPushButton("Save")
            save_btn.clicked.connect(self.save)
            controls_layout.addWidget(save_btn)

        controls_layout.addStretch()

        controls_widget = QWidget()
        controls_widget.setLayout(controls_layout)
        return controls_widget

    def deleteLater(self):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            shutil.rmtree(self.tmp.name, True)

        return super().deleteLater()

    def delete(self):
        index = self.main.tabs.indexOf(self)
        self.main.tabs.remove_tab(index)
