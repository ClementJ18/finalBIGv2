import io
import os
import tempfile
import threading
import traceback
import webbrowser

import audio_metadata
import tbm_utils
from PIL import Image
from PIL.ImageQt import ImageQt
from pyBIG import Archive
from pydub import AudioSegment
from pydub.playback import play
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from cah import CustomHero
from editor import Editor
from utils import SEARCH_HISTORY_MAX, decode_string, encode_string, unsaved_name

class GenericTab(QWidget):
    def __init__(self, tabs : QTabWidget, archive : Archive, name):
        super().__init__()

        self.archive = archive
        self.tabs = tabs

        self.name = name
        self.file_type = os.path.splitext(name)[1]
        self.data = self.archive.read_file(name)

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

class TextTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()
        self.text_widget = Editor(self.name)

        self.text_widget.setText(decode_string(self.data))
        self.text_widget.textChanged.connect(self.text_changed)

        layout.addWidget(self.text_widget)

        self.search_parameters = (None, False, False, False)

        search_widget = QWidget(self)
        layout.addWidget(search_widget)
        search_layout = QHBoxLayout()
        search_widget.setLayout(search_layout)

        if self.file_type in [".inc", ".ini"]:
            highlighting = QCheckBox("Highlighting")
            highlighting.setChecked(True)
            search_layout.addWidget(highlighting)
            highlighting.stateChanged.connect(self.text_widget.toggle_highlighting)

            dark_mode = QCheckBox("Dark Mode")
            dark_mode.setChecked(self.text_widget.lexer.dark_mode)
            search_layout.addWidget(dark_mode)
            dark_mode.stateChanged.connect(self.text_widget.toggle_dark_mode)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        search_layout.addWidget(self.search, stretch=5)

        self.search_button = QPushButton(self)
        self.search_button.setText("Search current file")
        self.search_button.clicked.connect(self.search_file)
        search_layout.addWidget(self.search_button)

        self.regex_box = QCheckBox("Regex")
        search_layout.addWidget(self.regex_box)

        self.case_box = QCheckBox("Case sensitive")
        search_layout.addWidget(self.case_box)

        self.whole_box = QCheckBox("Whole Word")
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

        if not any(self.search.itemText(x) == search for x in range(self.search.count())):
            self.search.addItem(search)

        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

    def save(self):
        self.archive.edit_file(self.name, encode_string(self.text_widget.text()))
        self.tabs.setTabText(self.tabs.currentIndex(), self.name)

    def text_changed(self):
        self.tabs.setTabText(self.tabs.currentIndex(), unsaved_name(self.name))


class ImageTab(GenericTab):
    def __init__(self, tabs: QTabWidget, archive: Archive, name):
        super().__init__(tabs, archive, name)

        self.scale = 1

    def generate_layout(self):
        layout = QVBoxLayout()

        img = Image.open(io.BytesIO(self.data))
        self.image = QPixmap.fromImage(ImageQt(img))

        self.label = QLabel(self)
        self.label.setScaledContents(True)
        self.label.setPixmap(self.image)
        layout.addWidget(self.label)

        self.setLayout(layout)

class CustomHeroTab(GenericTab):
    def generate_layout(self):
        layout = QHBoxLayout()

        try:
            cah = CustomHero(self.data)

            powers = "\n".join(
                f"\t- Level {level+1}: {power} (index: {index})"
                for power, level, index in cah.powers
            )
            blings = "\n".join(f"\t- {bling}: {index}" for bling, index in cah.blings)
            text = f"""
               Name: {cah.name}
               Colors: {cah.color1}, {cah.color2}, {cah.color3}

               Power: \n{powers}\n
               Blings: \n{blings}\n
            """
        except Exception as e:
            text = traceback.format_exc()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(text)

        layout.addWidget(data)
        self.setLayout(layout)

class SoundTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()

        self.song = AudioSegment.from_file(io.BytesIO(self.data), format=self.file_type[1:])

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
        t = threading.Thread(target=play, args=(self.song,))
        t.start()

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
        print("CLOSED")
        print(event)
        if event.src_path == self.tmp_name:
            self.tab.delete()
    

class MapTab(GenericTab):
    def __init__(self, tabs: QTabWidget, archive: Archive, name):
        super().__init__(tabs, archive, name)

        self.observer = None
        self.tmp = None

    def generate_layout(self, preview=False):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(f"Preview mode for {self.file_type} not supported, double click to edit.\n\n This will use the worldbuilder from your current game installation.")

        layout.addWidget(data)

        self.setLayout(layout)

        if preview:
            return

        self.tmp = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=self.file_type)
        self.tmp.write(self.data)
        self.tmp.close()

        webbrowser.open(self.tmp.name)

        self.observer = Observer()
        self.observer.schedule(SaveEventHandler(self, self.name, self.tmp.name), os.path.dirname(self.tmp.name))

        self.observer.start()

    def save(self):
        with open(self.tmp.name, "rb") as f:
            data = f.read()
            self.archive.edit_file(self.name, data)
            self.data = data

    def delete(self):
        index = self.tabs.indexOf(self)
        self.tabs.remove_tab(index)

    def deleteLater(self) -> None:
        if self.observer is not None:
            self.observer.stop()
            os.remove(self.tmp.name)

        return super().deleteLater()

    def generate_preview(self):
        self.generate_layout(preview=True)
        

TAB_TYPES = {
    (".lua", ".inc", ".ini", ".str", ".xml"): TextTab,
    (".bse", ".map"): MapTab,
    (".wav",): SoundTab,
    (".cah",): CustomHeroTab,
    (".tga", ".dds"): ImageTab,
}

def get_tab_from_file_type(name : str) -> GenericTab:
    file_type = os.path.splitext(name)[1]

    for key, value in TAB_TYPES.items():
        if file_type in key:
            return value
        
    return GenericTab
