from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from editor import Editor
from tabs.generic_tab import GenericTab
from utils import SEARCH_HISTORY_MAX, decode_string, encode_string, unsaved_name


class TextTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()
        self.text_widget = Editor(self.name, self.main.settings.dark_mode)

        string = decode_string(self.data, self.main.settings.encoding)
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

        layout.addWidget(self.generate_controller())
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
            with open(self.path, "r", encoding=self.main.settings.encoding) as f:
                data = f.read()
        else:
            data = self.text_widget.text()

        string = encode_string(data, self.main.settings.encoding)
        self.archive.edit_file(self.name, string)
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), self.name)

    def text_changed(self):
        self.main.tabs.setTabText(self.main.tabs.currentIndex(), unsaved_name(self.name))
