import os
import re

from PyQt6.Qsci import QsciLexerCustom, QsciLexerLua, QsciLexerXML, QsciScintilla
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from misc import SearchBox
from tabs.generic_tab import GenericTab
from utils.keywords import BEHAVIORS, CODEBLOCKS, KEYWORDS, SINGLETONS
from utils.utils import SEARCH_HISTORY_MAX, decode_string, encode_string, unsaved_name

KEYWORDS_PATTERN = re.compile(f"^({'|'.join(KEYWORDS)})$")
BEHAVIORS_PATTERN = re.compile(f"^({'|'.join(BEHAVIORS)})$")


class Commenter:
    def __init__(self, sci, comment_str):
        self.sci = sci
        self.comment_str = comment_str
        self.sel_regions = []

    def toggle_comments(self):
        lines = self.selected_lines()
        if len(lines) <= 0:
            return
        all_commented = True
        for line in lines:
            if not self.sci.text(line).strip().startswith(self.comment_str):
                all_commented = False
        if not all_commented:
            self.comment_lines(lines)
        else:
            self.uncomment_lines(lines)

    def selections(self):
        regions = []
        for i in range(self.sci.SendScintilla(QsciScintilla.SCI_GETSELECTIONS)):
            regions.append(
                {
                    "begin": self.sci.SendScintilla(QsciScintilla.SCI_GETSELECTIONNSTART, i),
                    "end": self.sci.SendScintilla(QsciScintilla.SCI_GETSELECTIONNEND, i),
                }
            )

        return regions

    def selected_lines(self):
        self.sel_regions = []
        all_lines = []
        regions = self.selections()
        for r in regions:
            start_line = self.sci.SendScintilla(QsciScintilla.SCI_LINEFROMPOSITION, r["begin"])
            end_line = self.sci.SendScintilla(QsciScintilla.SCI_LINEFROMPOSITION, r["end"])
            for cur_line in range(start_line, end_line + 1):
                if cur_line not in all_lines:
                    all_lines.append(cur_line)
            if r["begin"] <= r["end"]:
                self.sel_regions.append(r)
        return all_lines

    def comment_lines(self, lines):
        indent = self.sci.indentation(lines[0])
        for line in lines:
            indent = min(indent, self.sci.indentation(line))
        self.sci.beginUndoAction()
        for line in lines:
            self.adjust_selections(line, indent)
            self.sci.insertAt(self.comment_str, line, indent)
        self.sci.endUndoAction()
        self.restore_selections()

    def uncomment_lines(self, lines):
        self.sci.beginUndoAction()
        for line in lines:
            line_start = self.sci.SendScintilla(QsciScintilla.SCI_POSITIONFROMLINE, line)
            line_end = self.sci.SendScintilla(QsciScintilla.SCI_GETLINEENDPOSITION, line)
            if line_start == line_end:
                continue
            if line_end - line_start < len(self.comment_str):
                continue
            for c in range(line_start, line_end - len(self.comment_str) + 1):
                source_str = self.sci.text(c, c + len(self.comment_str))
                if source_str == self.comment_str:
                    self.sci.SendScintilla(QsciScintilla.SCI_DELETERANGE, c, len(self.comment_str))
                    break
        self.sci.endUndoAction()

    def restore_selections(self):
        if len(self.sel_regions) > 0:
            first = True
            for r in self.sel_regions:
                if first:
                    self.sci.SendScintilla(QsciScintilla.SCI_SETSELECTION, r["begin"], r["end"])
                    first = False
                else:
                    self.sci.SendScintilla(QsciScintilla.SCI_ADDSELECTION, r["begin"], r["end"])

    def adjust_selections(self, line, indent):
        for r in self.sel_regions:
            if self.sci.positionFromLineIndex(line, indent) <= r["begin"]:
                r["begin"] += len(self.comment_str)
                r["end"] += len(self.comment_str)
            elif self.sci.positionFromLineIndex(line, indent) < r["end"]:
                r["end"] += len(self.comment_str)


class LexerBFME(QsciLexerCustom):
    def __init__(self, parent, dark_mode) -> None:
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.first_pass = True
        self.toggled = True
        self.update_colors()

    def update_colors(self):
        if self.dark_mode:
            self.setColor(QColor(232, 232, 232, 1), 0)  # Style 0: light grey
            self.setColor(QColor(142, 79, 161, 204), 1)  # Style 1: purple
            self.setColor(QColor(222, 133, 222, 204), 2)  # Style 2: violet
            self.setColor(QColor(0, 135, 0, 204), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 204), 4)  # Style 4: red
            self.setColor(QColor(101, 87, 198, 204), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 204), 6)
            self.setColor(QColor(101, 187, 105, 204), 7)
            self.setColor(QColor(101, 176, 187, 204), 8)
            self.setColor(QColor(226, 103, 0, 204), 9)

            self.parent().setCaretForegroundColor(QColor(255, 255, 255, 73))
            self.setPaper(QColor(0, 0, 0, 0))
            self.setDefaultPaper(QColor(0, 0, 0, 0))
        else:
            self.setColor(QColor(0, 0, 0, 204), 0)  # Style 0: black
            self.setColor(QColor(105, 40, 124, 204), 1)  # Style 1: purple
            self.setColor(QColor(13, 0, 161, 204), 2)  # Style 2: blue
            self.setColor(QColor(59, 125, 61, 1), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 204), 4)  # Style 4: red
            self.setColor(QColor(50, 34, 166, 204), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 204), 6)
            self.setColor(QColor(101, 187, 105, 204), 7)
            self.setColor(QColor(101, 176, 187, 204), 8)
            self.setColor(QColor(226, 103, 0, 204), 9)

            self.parent().setCaretForegroundColor(QColor(0, 0, 0, 204))
            self.setPaper(QColor(255, 255, 255, 73))
            self.setDefaultPaper(QColor(255, 255, 255, 73))

    def language(self) -> str:
        return "BFMEini"

    def description(self, style: int) -> str:
        return f"Style_{style}"

    def styleText(self, start: int, end: int) -> None:
        if not self.toggled:
            return

        editor = self.parent()

        # Get raw bytes for the given range
        length = end - start
        byte_array = bytearray(length)
        ptr = memoryview(byte_array)
        editor.SendScintilla(editor.SCI_GETTEXTRANGE, start, end, ptr)

        try:
            text = byte_array.decode("utf-8")
        except UnicodeDecodeError:
            text = byte_array.decode("utf-8", errors="replace")

        self.startStyling(start)

        p = re.compile(r"[*]\/|\/[*]|\s+|\w+|\W")
        token_list = p.findall(text)

        apply_until_linebreak = None
        apply_to_next_token = None
        apply_to_string = None

        # Carry over style if we're in the middle of a comment/string
        if start > 0:
            # Get the byte before `start`
            prev_byte = bytearray(1)
            editor.SendScintilla(editor.SCI_GETTEXTRANGE, start - 1, start, memoryview(prev_byte))
            prev_char = prev_byte.decode("utf-8", errors="ignore") or ""

            prev_style = editor.SendScintilla(editor.SCI_GETSTYLEAT, start - 1)

            # Only continue if previous style was a comment and previous char wasn't newline
            if prev_style in [2, 3] and prev_char not in ("\n", "\r"):
                apply_until_linebreak = prev_style

        for token in token_list:
            token_bytes = token.encode("utf-8")
            byte_len = len(token_bytes)

            if apply_until_linebreak is not None:
                self.setStyling(byte_len, apply_until_linebreak)
                if "\n" in token:
                    apply_until_linebreak = None

            elif apply_to_next_token is not None:
                self.setStyling(byte_len, apply_to_next_token)
                apply_to_next_token = None

            elif apply_to_string is not None:
                self.setStyling(byte_len, apply_to_string)
                if token == '"':
                    apply_to_string = None

            else:
                if token[0].isdigit() or token[0] in ["%"]:
                    self.setStyling(byte_len, 1)
                elif token[0] == "#":
                    apply_to_next_token = 2
                    self.setStyling(byte_len, 2)
                elif token[0] in ["/", ";"]:
                    apply_until_linebreak = 3
                    self.setStyling(byte_len, 3)
                elif token[0].lower() in CODEBLOCKS:
                    self.setStyling(byte_len, 4)
                elif token[0].lower() in SINGLETONS:
                    self.setStyling(byte_len, 5)
                elif token.startswith('"'):
                    self.setStyling(byte_len, 6)
                    apply_to_string = 6
                elif BEHAVIORS_PATTERN.match(token):
                    self.setStyling(byte_len, 8)
                elif KEYWORDS_PATTERN.match(token):
                    self.setStyling(byte_len, 7)
                else:
                    self.setStyling(byte_len, 0)


class DefaultLexer(QsciLexerCustom):
    def __init__(self, parent, dark_mode) -> None:
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.first_pass = True
        self.toggled = True
        self.update_colors()

    def update_colors(self):
        if self.dark_mode:
            self.setColor(QColor(232, 232, 232, 255), 0)  # Style 0: light grey
            self.setColor(QColor(142, 79, 161, 204), 1)  # Style 1: purple
            self.setColor(QColor(222, 133, 222, 204), 2)  # Style 2: violet
            self.setColor(QColor(0, 135, 0, 204), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 204), 4)  # Style 4: red
            self.setColor(QColor(101, 87, 198, 204), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 204), 6)
            self.setColor(QColor(101, 187, 105, 204), 7)
            self.setColor(QColor(101, 176, 187, 204), 8)
            self.setColor(QColor(226, 103, 0, 204), 9)

            self.parent().setCaretForegroundColor(QColor(255, 255, 255, 73))
            self.setPaper(QColor(0, 0, 0, 0))
            self.setDefaultPaper(QColor(0, 0, 0, 0))
        else:
            self.setColor(QColor(0, 0, 0, 204), 0)  # Style 0: black
            self.setColor(QColor(105, 40, 124, 204), 1)  # Style 1: purple
            self.setColor(QColor(13, 0, 161, 204), 2)  # Style 2: blue
            self.setColor(QColor(59, 125, 61, 255), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 204), 4)  # Style 4: red
            self.setColor(QColor(50, 34, 166, 204), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 204), 6)
            self.setColor(QColor(101, 187, 105, 204), 7)
            self.setColor(QColor(101, 176, 187, 204), 8)
            self.setColor(QColor(226, 103, 0, 204), 9)

            self.parent().setCaretForegroundColor(QColor(0, 0, 0, 204))
            self.setPaper(QColor(255, 255, 255, 73))
            self.setDefaultPaper(QColor(255, 255, 255, 73))

    def language(self) -> str:
        return "BFMEstr"

    def description(self, style: int) -> str:
        return f"Style_{style}"

    def styleText(self, start: int, end: int) -> None:
        pass


class Editor(QsciScintilla):
    def __init__(self, file_name, dark_mode):
        super().__init__()

        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setIndentationGuides(True)
        self.setTabIndents(True)
        self.setAutoIndent(True)

        self.setMarginLineNumbers(0, True)
        self.setMarginWidth(0, "000000")

        self.SendScintilla(QsciScintilla.SCI_SETMULTIPLESELECTION, True)
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPASTE, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALSELECTIONTYPING, True)

        self.file_type = os.path.splitext(file_name)[1].lower()
        self.text_lexer = DefaultLexer(self, dark_mode)
        if self.file_type == ".lua":
            self.text_lexer = QsciLexerLua(self)
        elif self.file_type == ".xml":
            self.text_lexer = QsciLexerXML(self)
        elif self.file_type in (".ini", ".inc"):
            self.text_lexer = LexerBFME(self, dark_mode)

        self.setLexer(self.text_lexer)

        self.commenter = Commenter(self, ";")
        QShortcut(QKeySequence("Ctrl+;"), self, self.commenter.toggle_comments)

    def toggle_highlighting(self, state):
        if not isinstance(self.text_lexer, QsciLexerCustom):
            return

        self.text_lexer.toggled = state
        if state:
            self.text_lexer.styleText(0, len(self.text()))
        else:
            self.text_lexer.startStyling(0)
            self.text_lexer.setStyling(len(self.text()), 0)

    def toggle_dark_mode(self, state):
        if not isinstance(self.text_lexer, QsciLexerCustom):
            return

        self.text_lexer.dark_mode = state
        self.text_lexer.update_colors()
        self.toggle_highlighting(self.text_lexer.toggled)


class TextTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()
        self.text_widget = Editor(self.name, self.main.settings.dark_mode)

        string = decode_string(self.data, self.main.settings.encoding)
        self.text_widget.setText(string)
        self.text_widget.textChanged.connect(self.become_unsaved)

        layout.addWidget(self.text_widget)

        self.search_parameters = (None, False, False, False)

        search_widget = QWidget(self)
        layout.addWidget(search_widget)
        search_layout = QHBoxLayout()
        search_widget.setLayout(search_layout)

        if self.file_type in (".inc", ".ini", ".wnd", ".txt", ".xml", ".lua", ".str"):
            highlighting = QCheckBox("Highlighting")
            highlighting.setToolTip("Enable/disable syntax highlighting")
            highlighting.setChecked(True)
            search_layout.addWidget(highlighting)
            highlighting.stateChanged.connect(self.text_widget.toggle_highlighting)

        self.search = SearchBox(self, enter_callback=self.main.search_file)
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
        
        super().save()
