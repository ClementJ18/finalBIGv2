import os

from pyBIG.base_archive import BaseArchive
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QTextEdit

from tabs.generic_tab import GenericTab


class MapTab(GenericTab):
    def __init__(self, main: QMainWindow, archive: BaseArchive, name, preview):
        super().__init__(main, archive, name, preview)
        self.map_path = None

    def gather_files(self):
        folder = os.path.dirname(self.name)
        file_name = os.path.splitext(self.name)[0]

        to_extract = [
            self.name,
            f"{file_name}.tga",
            f"{file_name}_art.tga",
            f"{file_name}_pic.tga",
            f"{folder}\\map.ini",
            f"{folder}\\map.str",
        ]

        return to_extract

    def generate_layout(self, preview=False):
        self.open_externally()

    def save(self):
        with open(self.path, "rb") as f:
            data = f.read()
            self.archive.edit_file(self.name, data)
            self.data = data

    def generate_preview(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(
            f"Preview mode for {self.file_type} not supported, double click to edit.\n\n This will use the worldbuilder from your current game installation."
        )

        layout.addWidget(data)
        layout.addWidget(self.generate_controller())
        self.setLayout(layout)
