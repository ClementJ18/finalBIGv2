import os
import re
from PyQt6.QtGui import QColor, QShortcut, QKeySequence
from PyQt6.Qsci import QsciScintilla, QsciLexerLua, QsciLexerCustom, QsciLexerXML

import darkdetect

from keywords import KEYWORDS, BEHAVIORS, CODEBLOCKS, SINGLETONS

KEYWORDS_PATTERN = re.compile(f'^({"|".join(KEYWORDS)})$')
BEHAVIORS_PATTERN = re.compile(f'^({"|".join(BEHAVIORS)})$')


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
                if not cur_line in all_lines:
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
    def __init__(self, parent) -> None:
        super().__init__(parent)

        if darkdetect.isDark():
            self.setColor(QColor(232, 232, 232, 1), 0)  # Style 0: light grey
            self.setColor(QColor(142, 79, 161, 0.8), 1)  # Style 1: purple
            self.setColor(QColor(222, 133, 222, 0.8), 2)  # Style 2: violet
            self.setColor(QColor(0, 135, 0, 0.8), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 0.8), 4)  # Style 4: red
            self.setColor(QColor(101, 87, 198, 0.8), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 0.8), 6)
            self.setColor(QColor(101, 187, 105, 0.8), 7)
            self.setColor(QColor(101, 176, 187, 0.8), 8)
            self.setColor(QColor(226, 103, 0, 0.8), 9)

            self.parent().setCaretForegroundColor(QColor(255, 255, 255, 0.3))
        else:
            self.setColor(QColor(0, 0, 0, 0.8), 0)  # Style 0: black
            self.setColor(QColor(105, 40, 124, 0.8), 1)  # Style 1: purple
            self.setColor(QColor(13, 0, 161, 0.8), 2)  # Style 2: blue
            self.setColor(QColor(59, 125, 61, 1), 3)  # Style 3: green
            self.setColor(QColor(185, 40, 76, 0.8), 4)  # Style 4: red
            self.setColor(QColor(50, 34, 166, 0.8), 5)  # Style 5: Blue
            self.setColor(QColor(216, 210, 75, 0.8), 6)
            self.setColor(QColor(101, 187, 105, 0.8), 7)
            self.setColor(QColor(101, 176, 187, 0.8), 8)
            self.setColor(QColor(226, 103, 0, 0.8), 9)

            self.parent().setCaretForegroundColor(QColor(0, 0, 0, 0.8))

        self.first_pass = True
        self.toggled = True

    def language(self) -> str:
        return "BFMEini"

    def description(self, style: int) -> str:
        return f"Style_{style}"

    def styleText(self, start: int, end: int) -> None:
        if not self.toggled:
            return

        if self.first_pass:
            self.startStyling(0)
            text = self.parent().text()
            self.first_pass = False
        else:
            self.startStyling(start)
            text = self.parent().text()[start:end]

        p = re.compile(r"[*]\/|\/[*]|\s+|\w+|\W")
        # DO NOT CHANGE ENCODING
        token_list = [(token, len(bytearray(token, "utf-8"))) for token in p.findall(text)]

        editor = self.parent()
        apply_until_linebreak = None
        apply_to_next_token = None
        apply_to_string = None

        if start > 0:
            previous_style_nr = editor.SendScintilla(editor.SCI_GETSTYLEAT, start - 1)
            if previous_style_nr in [2, 3]:
                apply_until_linebreak = previous_style_nr

        for token in token_list:
            if apply_until_linebreak is not None:
                if "\n" in token[0]:
                    apply_until_linebreak = None
                    self.setStyling(token[1], 0)
                else:
                    self.setStyling(token[1], apply_until_linebreak)
            elif apply_to_next_token is not None:
                self.setStyling(token[1], apply_to_next_token)
                apply_to_next_token = None
            elif apply_to_string is not None:
                self.setStyling(token[1], apply_to_string)
                if token[0] == '"':
                    apply_to_string = None
            else:
                if token[0].isdigit() or token[0] in ["%"]:
                    self.setStyling(token[1], 1)
                elif token[0] == "#":
                    apply_to_next_token = 2
                    self.setStyling(token[1], 2)
                elif token[0] in ["/", ";"]:
                    apply_until_linebreak = 3
                    self.setStyling(token[1], 3)
                elif token[0].lower() in CODEBLOCKS:
                    self.setStyling(token[1], 4)
                elif token[0].lower() in SINGLETONS:
                    self.setStyling(token[1], 5)
                elif token[0].startswith('"'):
                    self.setStyling(token[1], 6)
                    apply_to_string = 6
                elif BEHAVIORS_PATTERN.match(token[0]):
                    self.setStyling(token[1], 8)
                elif KEYWORDS_PATTERN.match(token[0]):
                    self.setStyling(token[1], 7)
                else:
                    self.setStyling(token[1], 0)


class Editor(QsciScintilla):
    def __init__(self, file_name):
        super().__init__()

        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setIndentationGuides(True)
        self.setTabIndents(True)
        self.setAutoIndent(True)

        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(0, "000000")

        self.SendScintilla(QsciScintilla.SCI_SETMULTIPLESELECTION, True)
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPASTE, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALSELECTIONTYPING, True)

        self.file_type = os.path.splitext(file_name)[1]
        self.lexer = None
        if self.file_type == ".lua":
            self.lexer = QsciLexerLua(self)
        elif self.file_type == ".xml":
            self.lexer = QsciLexerXML(self)
        elif self.file_type in [".ini", ".inc"]:
            self.lexer = LexerBFME(self)

        self.setLexer(self.lexer)

        self.commenter = Commenter(self, ";")
        QShortcut(QKeySequence("Ctrl+;"), self, self.commenter.toggle_comments)

    def toggle_highlighting(self, state):
        if self.lexer is None:
            return

        self.lexer.toggled = state
        if state:
            self.lexer.styleText(0, len(self.text()))
        else:
            self.lexer.startStyling(0)
            self.lexer.setStyling(len(self.text()), 0)
