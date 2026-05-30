import re
from typing import TYPE_CHECKING

from pyBIG import base_archive
from PyQt6.QtCore import QEvent, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from file_views import file_view_mapping
from palette_themes import PALETTE_THEMES
from settings import OverwriteDefault
from utils.utils import ENCODING_LIST

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


class AddSummaryDialog(QDialog):
    """Resizable summary shown after add-to-archive operations.

    Unlike ``QMessageBox``, this dialog can be resized and maximized, so the
    "Show Details" list of new and overwritten files gets more room.
    """

    def __init__(
        self,
        message: str,
        new_names: list[str],
        overwritten_names: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Files added")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
            .pixmap(QSize(32, 32))
        )
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(icon)
        label = QLabel(message)
        label.setWordWrap(True)
        header.addWidget(label, 1)
        layout.addLayout(header)

        details_text = self._build_details(new_names, overwritten_names)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.details.setPlainText(details_text)
        self.details.setVisible(False)
        layout.addWidget(self.details, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        if details_text:
            self.toggle = buttons.addButton("Show Details", QDialogButtonBox.ButtonRole.ActionRole)
            self.toggle.setCheckable(True)
            self.toggle.toggled.connect(self._toggle_details)
        layout.addWidget(buttons)

        self.resize(420, 160)

    @staticmethod
    def _build_details(new_names: list[str], overwritten_names: list[str]) -> str:
        """New files first, then a separator, then overwritten files.

        Empty sections are omitted.
        """
        sections = []
        if new_names:
            sections.append(
                f"New files ({len(new_names)}):\n" + "\n".join(f"  {name}" for name in new_names)
            )
        if overwritten_names:
            sections.append(
                f"Overwritten files ({len(overwritten_names)}):\n"
                + "\n".join(f"  {name}" for name in overwritten_names)
            )
        return ("\n" + "─" * 40 + "\n").join(sections)

    def _toggle_details(self, shown: bool) -> None:
        self.details.setVisible(shown)
        self.toggle.setText("Hide Details" if shown else "Show Details")
        if shown and self.height() < 320:
            self.resize(self.width(), 360)


class SettingsDialog(QDialog):
    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.settings = main.settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.resize(580, 520)
        self._original_theme = self.settings.theme
        self._original_large_archive = self.settings.large_archive
        self._original_undo_size = self.settings.undo_stack_size

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(4, 4, 4, 4)

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        theme_entries = [("Dark (default)", "qdark"), ("Light", "qlight")]
        for key, (label, _scheme) in PALETTE_THEMES.items():
            theme_entries.append((label, key))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(160)
        for label, value in theme_entries:
            self.theme_combo.addItem(label, value)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == self.settings.theme:
                self.theme_combo.setCurrentIndex(i)
                break
        self.theme_combo.currentIndexChanged.connect(self._preview_theme)
        appearance_layout.addWidget(
            self._make_row(
                "Theme",
                "Color scheme for the application interface. Changes are previewed immediately.",
                self.theme_combo,
            )
        )
        content_layout.addWidget(appearance_group)

        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.external_check = QCheckBox()
        self.external_check.setChecked(self.settings.external)
        behavior_layout.addWidget(
            self._make_row(
                "Use External Programs",
                "Open files using the system's default application instead of "
                "the built-in editor.",
                self.external_check,
            )
        )

        self.smart_replace_check = QCheckBox()
        self.smart_replace_check.setChecked(self.settings.smart_replace_enabled)
        behavior_layout.addWidget(
            self._make_row(
                "Smart Replace",
                "When adding a file, try to match it to an existing archive entry by filename.",
                self.smart_replace_check,
            )
        )

        self.preview_check = QCheckBox()
        self.preview_check.setChecked(self.settings.preview_enabled)
        behavior_layout.addWidget(
            self._make_row(
                "Preview Files",
                "Show a preview tab automatically when a file is selected in the file list.",
                self.preview_check,
            )
        )

        self.add_summary_check = QCheckBox()
        self.add_summary_check.setChecked(self.settings.show_add_summary)
        behavior_layout.addWidget(
            self._make_row(
                "Show Add Summary",
                "Show a summary dialog with counts of new and overwritten files after adding files"
                " to the archive.",
                self.add_summary_check,
            )
        )

        self.default_view_combo = QComboBox()
        self.default_view_combo.setMinimumWidth(160)
        for view_type in file_view_mapping:
            self.default_view_combo.addItem(f"{view_type.capitalize()} View", view_type)
        for i in range(self.default_view_combo.count()):
            if self.default_view_combo.itemData(i) == self.settings.default_file_list_type:
                self.default_view_combo.setCurrentIndex(i)
                break
        behavior_layout.addWidget(
            self._make_row(
                "Default File View",
                "View type used when creating new file list tabs.",
                self.default_view_combo,
            )
        )
        content_layout.addWidget(behavior_group)

        file_ops_group = QGroupBox("File Operations")
        file_ops_layout = QVBoxLayout(file_ops_group)
        overwrite_opts = [
            ("Ask", OverwriteDefault.ASK),
            ("Overwrite", OverwriteDefault.OVERWRITE),
            ("Skip", OverwriteDefault.SKIP),
        ]

        self.extract_overwrite_combo = QComboBox()
        self.extract_overwrite_combo.setMinimumWidth(120)
        for label, value in overwrite_opts:
            self.extract_overwrite_combo.addItem(label, value)
        for i in range(self.extract_overwrite_combo.count()):
            if self.extract_overwrite_combo.itemData(i) == self.settings.extract_overwrite_default:
                self.extract_overwrite_combo.setCurrentIndex(i)
                break
        file_ops_layout.addWidget(
            self._make_row(
                "Extract Overwrite Default",
                "Default action when extracting a file that already exists at the destination.",
                self.extract_overwrite_combo,
            )
        )

        self.add_overwrite_combo = QComboBox()
        self.add_overwrite_combo.setMinimumWidth(120)
        for label, value in overwrite_opts:
            self.add_overwrite_combo.addItem(label, value)
        for i in range(self.add_overwrite_combo.count()):
            if self.add_overwrite_combo.itemData(i) == self.settings.add_overwrite_default:
                self.add_overwrite_combo.setCurrentIndex(i)
                break
        file_ops_layout.addWidget(
            self._make_row(
                "Add Overwrite Default",
                "Default action when adding a file whose name already exists in the archive.",
                self.add_overwrite_combo,
            )
        )
        content_layout.addWidget(file_ops_group)

        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)

        self.large_archive_check = QCheckBox()
        self.large_archive_check.setChecked(self.settings.large_archive)
        perf_layout.addWidget(
            self._make_row(
                "Large Archive Architecture",
                "Use a memory-efficient but slower system for very large archive files."
                " Requires a restart to take effect.",
                self.large_archive_check,
            )
        )

        self.undo_spin = QSpinBox()
        self.undo_spin.setRange(1, 500)
        self.undo_spin.setValue(self.settings.undo_stack_size)
        self.undo_spin.setMinimumWidth(80)
        perf_layout.addWidget(
            self._make_row(
                "Undo Stack Size",
                "Maximum number of undo steps kept in memory (1–500).",
                self.undo_spin,
            )
        )
        content_layout.addWidget(perf_group)

        adv_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout(adv_group)

        self.encoding_combo = QComboBox()
        self.encoding_combo.setMinimumWidth(160)
        self.encoding_combo.addItems(ENCODING_LIST)
        if self.settings.encoding in ENCODING_LIST:
            self.encoding_combo.setCurrentIndex(ENCODING_LIST.index(self.settings.encoding))
        adv_layout.addWidget(
            self._make_row(
                "Text Encoding",
                "Character encoding used when reading text files from the archive.",
                self.encoding_combo,
            )
        )
        content_layout.addWidget(adv_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self._cancel)
        outer.addWidget(buttons)

    def _make_row(self, name: str, description: str, widget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(16)

        text = QWidget()
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title = QLabel(f"<b>{name}</b>")
        desc = QLabel(description)
        desc.setWordWrap(True)
        f = desc.font()
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1))
        desc.setFont(f)

        text_layout.addWidget(title)
        text_layout.addWidget(desc)

        layout.addWidget(text, stretch=1)
        layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignVCenter)

        return row

    def _preview_theme(self, index: int):
        self.settings.set_theme(self.theme_combo.itemData(index))

    def _apply(self):
        self.settings.external = self.external_check.isChecked()
        self.settings.smart_replace_enabled = self.smart_replace_check.isChecked()
        self.settings.preview_enabled = self.preview_check.isChecked()
        self.settings.show_add_summary = self.add_summary_check.isChecked()
        self.settings.default_file_list_type = self.default_view_combo.currentData()
        self.settings.extract_overwrite_default = self.extract_overwrite_combo.currentData()
        self.settings.add_overwrite_default = self.add_overwrite_combo.currentData()
        self.settings.encoding = self.encoding_combo.currentText()

        if self.large_archive_check.isChecked() != self._original_large_archive:
            new_val = self.large_archive_check.isChecked()
            self.settings.large_archive = new_val
            state = "enabled" if new_val else "disabled"
            msg = (
                f"The large archive setting has been {state}. "
                "Please restart FinalBIGv2 to apply the change."
            )
            if new_val:
                msg += "\n\nNote: Large archives use less memory but may increase loading times."
            QMessageBox.information(self.main, "Large Archive Setting Changed", msg)

        new_undo = self.undo_spin.value()
        if new_undo != self._original_undo_size:
            self.settings.undo_stack_size = new_undo
            self.main.undo_stack.resize(new_undo)
            self.main.update_undo_redo_actions()

        self.accept()

    def _cancel(self):
        if self.settings.theme != self._original_theme:
            self.settings.set_theme(self._original_theme)
        self.reject()
