import re
from typing import TYPE_CHECKING

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from file_views import file_view_mapping

if TYPE_CHECKING:
    from main import MainWindow
    from tabs.generic_tab import GenericTab


class SearchBox(QComboBox):
    def __init__(self, *args, enter_callback=None, placeholder_text="Search...", **kwargs):
        super().__init__(*args, **kwargs)
        self.enter_callback = enter_callback
        self.setEditable(True)

        if placeholder_text:
            self.lineEdit().setPlaceholderText(placeholder_text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.enter_callback:
                self.enter_callback()
            return

        super().keyPressEvent(event)


class ArchiveSearchThread(QThread):
    matched = pyqtSignal(tuple)

    def __init__(
        self,
        parent: "MainWindow",
        search: str,
        encoding: str,
        archive: base_archive.BaseArchive,
        regex: bool,
    ) -> None:
        super().__init__(parent)

        self.search = search
        self.encoding = encoding
        self.archive = archive
        self.regex = regex

    def run(self):
        matches = []
        buffer = self.archive.bytes().decode(self.encoding)
        indexes = {
            match.start()
            for match in re.finditer(self.search if self.regex else re.escape(self.search), buffer)
        }
        match_count = len(indexes)

        for name, entry in self.archive.entries.items():
            matched_indexes = {
                index
                for index in indexes
                if entry.position <= index < (entry.position + entry.size)
            }
            if matched_indexes:
                indexes -= matched_indexes
                matches.append(name)

            if not indexes:
                break

        for name, modified_entry in self.archive.modified_entries.items():
            has_match = re.findall(
                self.search if self.regex else re.escape(self.search), modified_entry.content
            )
            if has_match:
                matches.append(name)

        self.matched.emit((matches, match_count))


class TabWidget(QTabWidget):
    def remove_tab(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()

        self.removeTab(index)

    def widget(self, index) -> "GenericTab":
        return super().widget(index)


class WrappingInputDialog(QDialog):
    def __init__(self, title="Input", label="Enter text:", parent=None, fixed_width: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(fixed_width)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))

        self.textEdit = QTextEdit()
        self.textEdit.setAcceptRichText(False)

        self.textEdit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.textEdit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        self.textEdit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.textEdit.installEventFilter(self)
        layout.addWidget(self.textEdit)

        self.textEdit.textChanged.connect(self.adjustHeightToContent)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.adjustHeightToContent()

    def adjustHeightToContent(self):
        viewport_width = self.textEdit.viewport().width()
        self.textEdit.document().setTextWidth(viewport_width)

        doc_height = self.textEdit.document().size().height()
        margins = self.textEdit.contentsMargins().top() + self.textEdit.contentsMargins().bottom()
        doc_margin = self.textEdit.document().documentMargin()

        line_height = self.textEdit.fontMetrics().lineSpacing()
        target_height = int(max(line_height * 1.6, doc_height + margins + doc_margin + 12))

        max_height = 300
        target_height = min(target_height, max_height)

        self.textEdit.setFixedHeight(target_height)

        self.adjustSize()

    def eventFilter(self, obj, event):
        if obj == self.textEdit and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept()
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def getText(
        parent=None, title="Input", label="Enter text:", default="", fixed_width: int = 500
    ):
        dialog = WrappingInputDialog(title, label, parent, fixed_width=fixed_width)
        dialog.textEdit.setPlainText(default)
        dialog.adjustHeightToContent()
        result = dialog.exec()
        text = dialog.textEdit.toPlainText().strip()
        ok = result == QDialog.DialogCode.Accepted
        return text, ok


class NewTabDialog(QDialog):
    def __init__(self, parent: "MainWindow" = None, default_name="List"):
        super().__init__(parent)
        self.setWindowTitle("New File Tab")
        self.setFixedWidth(400)
        self.parent_window = parent

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Tab name:"))
        self.name_input = QLineEdit()
        self.name_input.setText(default_name)
        self.name_input.selectAll()
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("\nView type:"))

        default_type = parent.settings.default_file_list_type
        self.button_group = QButtonGroup(self)

        for file_view_type in file_view_mapping:
            radio_button = QRadioButton(f"{file_view_type.capitalize()} View")
            radio_button.setChecked(default_type == file_view_type)
            self.button_group.addButton(radio_button)
            layout.addWidget(radio_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_input.setFocus()

    def validate_and_accept(self):
        """Validate the tab name before accepting the dialog"""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(
                self, "Invalid Name", "Tab name cannot be blank. Please enter a valid name."
            )
            self.name_input.setFocus()
            return

        existing_names = {
            self.parent_window.listwidget.tabText(i)
            for i in range(self.parent_window.listwidget.count() - 1)
        }

        if name in existing_names:
            QMessageBox.warning(
                self,
                "Duplicate Name",
                f"A tab named '{name}' already exists. Please choose a different name.",
            )
            self.name_input.selectAll()
            self.name_input.setFocus()
            return

        self.accept()

    def get_values(self):
        """Returns (name, widget_type) where widget_type is 'tree' or 'list'"""
        name = self.name_input.text().strip()
        checked_button = self.button_group.checkedButton()
        widget_type = checked_button.text().split()[0].lower()
        return name, widget_type
