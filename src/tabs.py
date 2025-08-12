import io
import os
import shutil
import struct
import tempfile
import traceback
import webbrowser

from PIL import Image
from PIL.ImageQt import ImageQt
import audio_metadata
from pyBIG.base_archive import BaseArchive
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)
import playsound
import tbm_utils
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from cah import CustomHero
from editor import Editor
from utils import SEARCH_HISTORY_MAX, decode_string, encode_string, unsaved_name


class GenericTab(QWidget):
    def __init__(self, main: QMainWindow, archive: BaseArchive, name):
        super().__init__(main)

        self.archive = archive
        self.main = main

        self.name = name
        self.file_type = os.path.splitext(name)[1]
        self.data = self.archive.read_file(name)

        self.external = False
        self.path = None

    def generate_layout(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(f"{self.file_type} is not currently supported")

        layout.addWidget(data)

        self.setLayout(layout)

    def generate_preview(self):
        self.generate_layout()

    def save(self):
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
        webbrowser.open(self.path)

        self.observer = Observer()
        self.observer.schedule(SaveEventHandler(self, self.name, self.path), self.tmp.name)

        self.observer.start()
        self.external = True


class TextTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()
        self.text_widget = Editor(self.name, self.main.dark_mode)

        string = decode_string(self.data, self.main.encoding)
        self.text_widget.setText(string)
        self.text_widget.textChanged.connect(self.text_changed)

        layout.addWidget(self.text_widget)

        self.search_parameters = (None, False, False, False)

        search_widget = QWidget(self)
        layout.addWidget(search_widget)
        search_layout = QHBoxLayout()
        search_widget.setLayout(search_layout)

        if self.file_type.lower() in (".inc", ".ini", ".wnd", ".txt", ".xml", ".lua", ".str"):
            highlighting = QCheckBox("Highlighting")
            highlighting.setToolTip("Enable/disable syntax highlighting")
            highlighting.setChecked(True)
            search_layout.addWidget(highlighting)
            highlighting.stateChanged.connect(self.text_widget.toggle_highlighting)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        completer = self.search.completer()
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.search.setCompleter(completer)
        search_layout.addWidget(self.search, stretch=5)

        self.search_button = QPushButton(self)
        self.search_button.setText("Search current file")
        self.search_button.clicked.connect(self.search_file)
        search_layout.addWidget(self.search_button)

        self.regex_box = QCheckBox("Regex")
        self.regex_box.setToolTip("Intepret search text as a regex pattern?")
        search_layout.addWidget(self.regex_box)

        self.case_box = QCheckBox("Case sensitive")
        self.case_box.setToolTip("Match case of search?")
        search_layout.addWidget(self.case_box)

        self.whole_box = QCheckBox("Whole Word")
        self.whole_box.setToolTip("Match only whole words?")
        search_layout.addWidget(self.whole_box)

        self.setLayout(layout)

    def generate_preview(self):
        self.generate_layout()
        self.text_widget.setReadOnly(True)

    def search_file(self):
        search = self.search.currentText()
        regex = self.regex_box.isChecked()
        case = self.case_box.isChecked()
        whole = self.whole_box.isChecked()
        search_parameters = (search, regex, case, whole)

        if search_parameters != self.search_parameters:
            self.search_parameters = search_parameters
            self.text_widget.findFirst(search, regex, case, whole, True)
        else:
            self.text_widget.findNext()

        if search and not any(
            self.search.itemText(x) == search for x in range(self.search.count())
        ):
            self.search.addItem(search)

        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

        self.search.setFocus()

    def save(self):
        if self.external:
            with open(self.path, "r", encoding=self.main.encoding) as f:
                data = f.read()
        else:
            data = self.text_widget.text()

        string = encode_string(data, self.main.encoding)
        self.archive.edit_file(self.name, string)
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), self.name)

    def text_changed(self):
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), unsaved_name(self.name))


class ImageTab(GenericTab):
    def __init__(self, main: QMainWindow, archive: BaseArchive, name):
        super().__init__(main, archive, name)

        self.scale = 1
        self.image = None
        self.qimage = None
        self.pixmap = None
        self.image_label = None
        self.showing_alpha = False

    @staticmethod
    def _get_dds_mipmap_count(dds_data: bytes) -> int:
        if len(dds_data) < 32:
            return 1

        dwFlags = struct.unpack_from("<I", dds_data, 8)[0]
        if dwFlags & 0x20000:
            return struct.unpack_from("<I", dds_data, 28)[0]

        return 1

    @staticmethod
    def _get_dds_format(dds_data: bytes) -> str:
        if len(dds_data) < 88:
            return "N/A"

        if struct.unpack_from("<I", dds_data, 80)[0] & 0x4:
            return (
                struct.unpack_from("<4s", dds_data, 84)[0].decode("ascii", errors="ignore").strip()
            )
        else:
            return "Uncompressed"

    def generate_layout(self):
        main_layout = QVBoxLayout(self)
        self.image_label = QLabel(self)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        controls_layout = QHBoxLayout()

        self.alpha_button = QPushButton("Show Alpha")
        self.alpha_button.clicked.connect(self.toggle_alpha_view)
        controls_layout.addWidget(self.alpha_button)

        main_layout.addLayout(controls_layout)

        try:
            self.image = Image.open(io.BytesIO(self.data))

            if self.image.mode not in ("RGBA", "LA"):
                self.alpha_button.setEnabled(False)

            width, height = self.image.size
            controls_layout.addWidget(QLabel(f"<b>Dimensions:</b> {width}x{height}"))

            if self.file_type.lower() == ".tga":
                bit_depth = {"RGBA": "32-bit", "RGB": "24-bit"}.get(self.image.mode, "N/A")
                controls_layout.addWidget(QLabel(f"<b>Format:</b> {bit_depth}"))
            elif self.file_type.lower() == ".dds":
                controls_layout.addWidget(
                    QLabel(f"<b>Format:</b> {self._get_dds_format(self.data)}")
                )
                controls_layout.addWidget(
                    QLabel(f"<b>Mipmaps:</b> {self._get_dds_mipmap_count(self.data)}")
                )

            controls_layout.addStretch()
            self.update_display()
        except Exception as e:
            error_box = QTextEdit(self)
            error_box.setReadOnly(True)
            error_box.setText(f"Couldn't display image:\n{e}\n\n{traceback.format_exc()}")
            main_layout.addWidget(error_box)

    def toggle_alpha_view(self):
        self.showing_alpha = not self.showing_alpha
        self.update_display()

    def update_display(self):
        if not self.image:
            return

        display_image = self.image.getchannel("A") if self.showing_alpha else self.image
        self.alpha_button.setText("Show Color" if self.showing_alpha else "Show Alpha")
        self.qimage = ImageQt(display_image)
        self.pixmap = QPixmap.fromImage(self.qimage)
        self.image_label.setPixmap(self.pixmap)


class CustomHeroTab(GenericTab):
    def generate_layout(self):
        layout = QHBoxLayout()

        try:
            cah = CustomHero(self.data, self.main.encoding)

            powers = "\n".join(
                f"\t- Level {level + 1}: {power} (index: {index})"
                for power, level, index in cah.powers
            )
            blings = "\n".join(f"\t- {bling}: {index}" for bling, index in cah.blings)
            text = f"""
               Name: {cah.name}
               Colors: {cah.color1}, {cah.color2}, {cah.color3}

               Power: \n{powers}\n
               Blings: \n{blings}\n
            """
        except Exception:
            text = traceback.format_exc()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(text)

        layout.addWidget(data)
        self.setLayout(layout)


class SoundTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()

        with tempfile.NamedTemporaryFile(delete=False, suffix=self.file_type) as f:
            f.write(self.data)
            self.path = f.name

        play_button = QPushButton(self)
        play_button.setText("Play")
        play_button.clicked.connect(self.play_audio)
        layout.addWidget(play_button)

        metadata = audio_metadata.loads(self.data)

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(
            f"""
            File: {self.name}
            Size: {tbm_utils.humanize_filesize(metadata.filesize)}
            Duration: {tbm_utils.humanize_duration(metadata.streaminfo.duration)}
            """
        )

        layout.addWidget(data)
        self.setLayout(layout)

    def play_audio(self):
        playsound.playsound(self.path, False)


class SaveEventHandler(FileSystemEventHandler):
    def __init__(self, tab, name, tmp_name):
        super().__init__()

        self.tab = tab
        self.file_name = name
        self.tmp_name = tmp_name

    def on_modified(self, event):
        if event.src_path == self.tmp_name:
            self.tab.save()

    def on_closed(self, event):
        if event.src_path == self.tmp_name:
            self.tab.delete()


class MapTab(GenericTab):
    def __init__(self, main: QMainWindow, archive: BaseArchive, name):
        super().__init__(main, archive, name)

        self.observer = None
        self.map_path = None
        self.tmp = None

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

    def delete(self):
        index = self.main.tabs.indexOf(self)
        self.main.tabs.remove_tab(index)

    def deleteLater(self) -> None:
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            shutil.rmtree(self.tmp.name, True)

        return super().deleteLater()

    def generate_preview(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(
            f"Preview mode for {self.file_type} not supported, double click to edit.\n\n This will use the worldbuilder from your current game installation."
        )

        layout.addWidget(data)
        self.setLayout(layout)


TAB_TYPES = {
    (".bse", ".map"): MapTab,
    (".wav", ".mp3"): SoundTab,
    (".cah",): CustomHeroTab,
    tuple(Image.registered_extensions().keys()): ImageTab,
}


def get_tab_from_file_type(name: str) -> GenericTab:
    file_type = os.path.splitext(name)[1].lower()

    for key, value in TAB_TYPES.items():
        if file_type in key:
            return value

    return TextTab
