import fnmatch
import re
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from misc import ArchiveSearchThread
from utils import SEARCH_HISTORY_MAX

if TYPE_CHECKING:
    from main import MainWindow


class SearchManager:
    def search_archive(self: "MainWindow", regex):
        search, ok = QInputDialog.getText(
            self,
            "Search archive",
            f"This will search through the currently filtered list. Search keyword{' (Regex)' if regex else ''}:",
        )
        if not ok:
            return

        def update_list_with_matches(returned):
            matches = returned[0]
            for x in range(self.listwidget.active_list.count()):
                item = self.listwidget.active_list.item(x)

                if not item.isHidden():
                    item.setHidden(item.text() not in matches)

            self.message_box.done(1)
            QMessageBox.information(
                self,
                "Search finished",
                f"Found <b>{returned[1]}</b> instances over <b>{len(matches)}</b> files. Filtering list.",
            )

        self.message_box = QMessageBox(
            QMessageBox.Icon.Information,
            "Search in progress",
            "Searching the archive, please wait...",
            QMessageBox.StandardButton.Ok,
            self,
        )
        self.message_box.button(QMessageBox.StandardButton.Ok).setEnabled(False)

        self.search_thread = ArchiveSearchThread(
            self, search, self.settings.encoding, self.archive, regex
        )
        self.search_thread.matched.connect(update_list_with_matches)
        self.search_thread.start()
        self.message_box.exec()

    def search_file(self: "MainWindow"):
        index = self.tabs.currentIndex()
        if index < 0:
            return

        widget = self.tabs.widget(index)
        if hasattr(widget, "search_file"):
            widget.search_file()

    def filter_list(self: "MainWindow"):
        search = self.search.currentText()
        invert = self.invert_box.isChecked()
        re_filter = self.re_filter_box.isChecked()
        use_regex = self.regex_filter_box.isChecked()
        active_list = self.listwidget.active_list
        files = active_list.files_list

        if use_regex:
            pattern = re.compile(search, re.IGNORECASE)

        for i, text in enumerate(files):
            item = active_list.item(i)
            if item.isHidden() and re_filter:
                continue

            if search:
                if use_regex:
                    match = bool(pattern.search(text))
                else:
                    match = fnmatch.fnmatch(text, f"*{search}*")
                item.setHidden(not (match ^ invert))
            else:
                item.setHidden(False)

        if search:
            existing_searches = [self.search.itemText(x) for x in range(self.search.count())]
            if search not in existing_searches:
                self.search.addItem(search)
            if self.search.count() > SEARCH_HISTORY_MAX:
                self.search.removeItem(0)
