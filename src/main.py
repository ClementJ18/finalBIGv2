import io
import os
import fnmatch
import sys
import threading
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QListWidget, QSplitter,
    QHBoxLayout, QWidget, QTabWidget, QPushButton, 
    QVBoxLayout, QComboBox, QMessageBox, QFileDialog, QAbstractItemView,
    QInputDialog, QCheckBox, QTextEdit, QLabel
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QShortcut, QPixmap
)
from PyQt6.QtCore import Qt

from pyBIG import Archive
from pydub import AudioSegment
from pydub.playback import play
import audio_metadata
import tbm_utils
from PIL import Image
from PIL.ImageQt import ImageQt

from editor import Editor
from cah import CustomHero
import traceback

SEARCH_HISTORY_MAX = 15
HELP_STRING = """
<h2>Shortcuts</h2>
<ul>
    <li> <b>Ctrl+S</b> : Save current file </br> </li>
    <li> <b>Ctrl+;</b> : Comment/Uncomment line/block </br> </li>
    <li> <b>Return</b> : Search/Find next when done in a search box </br> </li>
</ul> 
"""

ABOUT_STRING = """
<h2>About</h2>
<b>FinalBIGv2</b> was made by officialNecro because he was getting very annoyed at
FinalBIG crashing all the time. <br/>

Source code is available <a href="https://github.com/ClementJ18/finalBIGv2">here</a>. Suggestions and bug reports should also go there. <br/><br/>

Version: <b>0.1.0</b>
"""

def name_normalizer(name):
    return name.replace("/", "\\")

class EditorTab(QWidget):
    def __init__(self, tabs : QTabWidget, archive : Archive, name, text):
        super().__init__()
        self.archive = archive
        self.name = name
        self.tabs = tabs
        self.changed = False
        self.scale = 1

        self.file_type = os.path.splitext(name)[1]
        if self.file_type in [".lua", ".inc", ".ini", ".str", ".xml"]:
            self.setLayout(self.generate_text_editor(text))
        elif self.file_type in [".bse", ".map"]:
            self.setLayout(self.generate_unsupported())
        elif self.file_type in [".wav"]:
            self.setLayout(self.generate_audio_listener())
        elif self.file_type in [".cah"]:
            self.setLayout(self.generate_cah_viewer())
        elif self.file_type in [".tga", ".dds"]:
            self.setLayout(self.generate_image_viewer())
        else:
            self.setLayout(self.generate_unsupported())

    def generate_image_viewer(self):
        layout = QVBoxLayout()

        img_bytes = self.archive.read_file(self.name)
        img = Image.open(io.BytesIO(img_bytes))
        self.image = QPixmap.fromImage(ImageQt(img))
        
        self.label = QLabel(self)
        self.label.setScaledContents(True)
        self.label.setPixmap(self.image)
        layout.addWidget(self.label)

        return layout

    def generate_cah_viewer(self):
        layout = QHBoxLayout()

        try:
            cah = CustomHero(self.archive.read_file(self.name))
        except Exception as e:
            text = str(e)

        try:
            powers = "\n".join(f"\t- Level {level+1}: {power} (index: {index})" for power, level, index in cah.powers)
            blings = "\n".join(f"\t- {bling}: {index}" for bling, index in cah.blings)
            text = f"""
               Name: {cah.name}
               Colors: {cah.color1}, {cah.color2}, {cah.color3}

               Power: \n{powers}\n
               Blings: \n{blings}\n
            """
        except Exception as e:
            text = str(e)

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(text)

        layout.addWidget(data)

        return layout

    def generate_unsupported(self):
        layout = QHBoxLayout()

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(f"{self.file_type} is not currently supported")

        layout.addWidget(data)

        return layout

    def generate_audio_listener(self):
        layout = QVBoxLayout()

        data = self.archive.read_file(self.name)
        self.song = AudioSegment.from_file(io.BytesIO(data), format=self.file_type[1:])

        play_button = QPushButton(self)
        play_button.setText("Play")
        play_button.clicked.connect(self.play_audio)
        layout.addWidget(play_button)

        metadata = audio_metadata.loads(data)

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

        return layout

    def generate_text_editor(self, text):
        layout = QVBoxLayout()
        self.text = Editor(self.name)

        self.text.setText(text)
        self.text.textChanged.connect(self.text_changed)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.text)
        save_shortcut.activated.connect(self.save_text)

        layout.addWidget(self.text)

        self.search_parameters = (None, False, False, False)
        
        search_widget = QWidget(self)
        layout.addWidget(search_widget)
        search_layout = QHBoxLayout()
        search_widget.setLayout(search_layout)

        highlighting = QCheckBox("Highlighting")
        highlighting.setChecked(True)
        search_layout.addWidget(highlighting)
        highlighting.stateChanged.connect(self.text.toggle_highlighting)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.search)
        shortcut.activated.connect(self.search_file)
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

        return layout

    def search_file(self):
        search = self.search.currentText()
        regex = self.regex_box.isChecked()
        case = self.case_box.isChecked()
        whole = self.whole_box.isChecked()
        search_parameters = (search, regex, case, whole)

        if search_parameters != self.search_parameters:
            self.search_parameters = search_parameters
            self.text.findFirst(
                search,
                regex,
                case,
                whole,
                True
            )
        else:
            self.text.findNext()

        if not any(self.search.itemText(x) == search for x in range(self.search.count())):
            self.search.addItem(search)
        
        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

    def save_text(self):
        self.archive.edit_file(self.name, self.text.text().encode("Latin-1"))
        self.changed = False
        self.tabs.setTabText(self.tabs.currentIndex(), self.name)

    def text_changed(self):
        self.changed = True
        self.tabs.setTabText(self.tabs.currentIndex(), f"{self.name} *")

    def play_audio(self):
        t = threading.Thread(target=play, args=(self.song,))
        t.start()

class FileList(QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

        self.main : MainWindow = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if os.path.isfile(url.path()):
                    self.add_file(url.path())
                else:
                    self.add_folder(url.path())

            self.main.archive.repack()
            self.update_list()    
            event.acceptProposedAction()

    def add_file(self, url, blank=False):
        name, ok = QInputDialog.getText(self, "Filename", "Save the file under the following name:", text=url)
        if not ok:
            return False

        if self.main.archive.file_exists(name):
            ret = QMessageBox.question(
                self,
                'Overwrite file?', 
                "This file already exists, overwrite?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                return False
            
            self.main.archive.remove_file(name)

        try:
            if blank:
                self.main.archive.add_file(name, b'')
            else:
                with open(url, "rb") as f:
                    self.main.archive.add_file(name, f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return False

        return True

    def add_folder(self, url):
        skip_all = False
        common_dir = os.path.dirname(url)
        for root, _, files in os.walk(url):
            for f in files:
                full_path = os.path.join(root, f)
                name = name_normalizer(os.path.relpath(full_path, common_dir))

                if self.main.archive.file_exists(name):
                    if not skip_all:
                        ret = QMessageBox.question(
                            self,
                            'Overwrite file?', 
                            "This file already exists, overwrite?", 
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.YesToAll
                        )
                        if ret == QMessageBox.StandardButton.No:
                            continue

                        if ret == QMessageBox.StandardButton.YesToAll:
                            skip_all = True

                    self.main.archive.remove_file(name)

                with open(full_path, "rb") as f:
                    self.main.archive.add_file(name, f.read())

    def update_list(self):
        self.clear()
        for index, entry in enumerate(self.main.archive.entries):
            self.insertItem(index, entry)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_name = "FinalBIG v2"

        try:
            path_arg = sys.argv[1]
        except IndexError:
            path_arg = ""

        if os.path.exists(path_arg):
            self.path = path_arg
            with open(self.path, "rb") as f:
                self.archive = Archive(f.read())
            
            self.setWindowTitle(f"{os.path.basename(self.path)} - {self.base_name}")
        else:
            self.path = None
            self.archive = Archive()
            self.setWindowTitle(f"Untitled Archive - {self.base_name}")

        layout = QVBoxLayout()
        
        self.create_menu()

        self.listwidget = FileList(self)
        self.listwidget.doubleClicked.connect(self.file_clicked)

        self.listwidget.update_list()

        search_widget = QWidget(self)
        search_layout = QHBoxLayout()
        layout.addWidget(search_widget, stretch=1)
        search_widget.setLayout(search_layout)

        self.search = QComboBox(self)
        self.search.setEditable(True)
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.search)
        shortcut.activated.connect(self.filter_list)
        search_layout.addWidget(self.search, stretch=5)

        self.search_button = QPushButton(self)
        self.search_button.setText("Filter file list")
        self.search_button.clicked.connect(self.filter_list)
        search_layout.addWidget(self.search_button, stretch=1)

        self.tabs = QTabWidget(self)
        self.tabs.setElideMode(Qt.TextElideMode.ElideLeft)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setUsesScrollButtons(False)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self.listwidget)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 200)
        layout.addWidget(splitter, stretch=100)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.showMaximized()

    def filter_list(self):
        search = self.search.currentText()
        for x in range(self.listwidget.count()):
            item = self.listwidget.item(x)

            if search == "":
                item.setHidden(False)
            else:
                item.setHidden(not fnmatch.fnmatchcase(item.text(), search))

        if search == "":
            return

        if not any(self.search.itemText(x) == search for x in range(self.search.count())):
            self.search.addItem(search)
        
        if self.search.count() > SEARCH_HISTORY_MAX:
            self.search.removeItem(0)

    def create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        new_action = QAction("New", self)
        file_menu.addAction(new_action)
        new_action.triggered.connect(self.new)

        open_action = QAction("Open", self)
        file_menu.addAction(open_action)
        open_action.triggered.connect(self.open)

        save_action = QAction("Save", self)
        file_menu.addAction(save_action)
        save_action.triggered.connect(self.save)

        save_as_action = QAction("Save as...", self)
        file_menu.addAction(save_as_action)
        save_as_action.triggered.connect(self.save_as)
        
        edit_menu = menu.addMenu("&Edit")

        new_file_action = QAction("New file", self)
        edit_menu.addAction(new_file_action)
        new_file_action.triggered.connect(self.new_file)

        add_file_action = QAction("Add file", self)
        edit_menu.addAction(add_file_action)
        add_file_action.triggered.connect(self.add_file)

        add_dir_action = QAction("Add directory", self)
        edit_menu.addAction(add_dir_action)
        add_dir_action.triggered.connect(self.add_directory)

        delete_action = QAction("Delete file", self)
        edit_menu.addAction(delete_action)
        delete_action.triggered.connect(self.delete)

        edit_menu.addSeparator()

        extract_action = QAction("Extract file", self)
        edit_menu.addAction(extract_action)
        extract_action.triggered.connect(self.extract)

        extract_all_action = QAction("Extract All", self)
        edit_menu.addAction(extract_all_action)
        extract_all_action.triggered.connect(self.extract_all)

        tools_menu = menu.addMenu("&Tools")

        dump_list_action = QAction("Dump File List", self)
        tools_menu.addAction(dump_list_action)
        dump_list_action.triggered.connect(self.dump_list)

        option_menu = menu.addMenu("&Help")

        about_action = QAction("About", self)
        option_menu.addAction(about_action)
        about_action.triggered.connect(self.show_about)

        help_action = QAction("Help", self)
        option_menu.addAction(help_action)
        help_action.triggered.connect(self.show_help)

    def show_help(self):
        QMessageBox.information(
            self, 
            "Help",
            HELP_STRING
        )

    def show_about(self):
        QMessageBox.information(
            self, 
            "About",
            ABOUT_STRING
        )

    def dump_list(self):
        file = QFileDialog.getSaveFileName(self, "Save dump", os.getcwd())[0]

        if not file:
            return
        
        self.archive.repack()
        with open(file, "w") as f:
            f.write("\n".join(name for name in self.archive.entries))

        QMessageBox.information(self, "Dump Generated", "File list dump has been created")

    def new(self):
        if not self.close_unsaved():
            return

        self.archive = Archive()
        self.path = None
        self.listwidget.update_list()
        self.setWindowTitle(f"Untitled Archive - {self.base_name}")

    def open(self):
        if not self.close_unsaved():
            return

        file = QFileDialog.getOpenFileName(self, 'Open file', '',"BIG files (*.big)")
        if not file[0]:
            return

        try:
            self.path = file[0]
            with open(self.path, "rb") as f:
                self.archive = Archive(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

        self.setWindowTitle(f"{os.path.basename(self.path)} - {self.base_name}")
        self.listwidget.update_list()

    def save(self):
        self._save(self.path)

    def save_as(self):
        self._save(None)

    def _save(self, path):
        if path is None:
            path = QFileDialog.getSaveFileName(self, "Save archive", os.getcwd())[0]

        if not path:
            return

        for index in range(self.tabs.count()):
            if "*" in self.tabs.tabText(index):
                self.tabs.widget(index).save_text()

        self.archive.save(path)
        QMessageBox.information(self, "Done", "Archive has been saved")
        self.path = path
        self.setWindowTitle(f"{os.path.basename(self.path)} - {self.base_name}")

    def add_file(self):
        file = QFileDialog.getOpenFileName(self, "Add file", os.getcwd())
        if not file[0]:
            return

        self.listwidget.add_file(file[0])

        self.archive.repack()
        self.listwidget.update_list()  

    def add_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Add directory", os.getcwd())
        if not path[0]:
            return

        self.listwidget.add_folder(path[0])

        self.archive.repack()
        self.listwidget.update_list() 

    def new_file(self):
        self.listwidget.add_file(None, blank=True)

        self.archive.repack()
        self.listwidget.update_list()

    def file_selected(self):
        if self.listwidget.currentItem() is None:
            QMessageBox.warning(self, "No file selected", "You have not selected a file")
            return False
        
        return True

    def delete(self):
        if not self.file_selected():
            return

        item = self.listwidget.currentItem()
        name = item.text()
        ret = QMessageBox.question(
            self,
            'Delete file?', 
            f"Are you sure you want to delete {name}?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.No:
            return

        self.archive.remove_file(name)
        self.listwidget.update_list()


    def extract(self):
        if not self.file_selected():
            return

        name = self.listwidget.currentItem().text()
        file_name = name.split("\\")[-1]
        path = QFileDialog.getSaveFileName(self, 'Extract file', os.path.join(os.getcwd(), file_name))
        if not path:
            return

        with open(path, "wb") as f:
            f.write(self.archive.read_file(name))

        QMessageBox.information(self, "Done", "File has been extracted")        

    def extract_all(self):
        path = QFileDialog.getExistingDirectory(self, 'Extract file all files to directory', os.getcwd())
        if not path:
            return

        self.archive.extract(path)
        QMessageBox.information(self, "Done", "All files have been extracted")

    def file_clicked(self, qmodelindex):
        name = self.listwidget.currentItem().text()

        for x in range(self.tabs.count()):
            if self.tabs.tabText(x) == name:
                self.tabs.setCurrentIndex(x)
                break
        else:
            self.add_tab(name)

    def add_tab(self, entry):
        text = self.archive.read_file(entry).decode("Latin-1")
        self.tabs.addTab(EditorTab(self.tabs, self.archive, entry, text), entry)
        self.tabs.setCurrentIndex(self.tabs.count()-1)

    def close_tab(self, index):
        if self.tabs.widget(index).changed:
            ret = QMessageBox.question(
                self,
                'Close unsaved?', 
                "There is unsaved work, are you sure you want to close?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                return

        self.tabs.widget(index).deleteLater()
        self.tabs.removeTab(index)

    def close_unsaved(self):
        unsaved_tabs = any("*" in self.tabs.tabText(i) for i in range(self.tabs.count()))
        if self.archive.modified_entries or unsaved_tabs:
            ret = QMessageBox.question(
                self,
                'Close unsaved?', 
                "There is unsaved work, are you sure you want to close?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                return False

        self.tabs.clear()
        return True

    def closeEvent(self, event):
        if self.close_unsaved():
            event.accept()
        else:
            event.ignore()
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    
    try:
        app.exec()
    except Exception as exception:
        with open("error.log", "w") as error_file:
            traceback.print_exc(file=error_file)
