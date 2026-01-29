import fnmatch
import re
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from file_views import FileViewAbstract
from misc import ArchiveSearchThread
from utils.utils import SEARCH_HISTORY_MAX

if TYPE_CHECKING:
    from main import MainWindow


class SearchManager:
    def search_archive(self: "MainWindow", regex):
        search, ok = QInputDialog.getText(
            self,
            "Search archive",
            f"This will search through the file list. Search keyword{' (Regex)' if regex else ''}:",
        )
        if not ok:
            return

        def update_list_with_matches(returned):
            matches = returned[0]
            for item in self.listwidget.active_list.get_items():
                item.setHidden(self.listwidget.active_list.get_item_path(item) not in matches)

            self.listwidget.active_list.post_filter()

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
        widget.search()

    def filter_list_from_search(self: "MainWindow"):
        search = self.search.currentText().strip()
        invert = self.invert_box.isChecked()
        re_filter = self.re_filter_box.isChecked()
        use_regex = self.regex_filter_box.isChecked()
        active_list = self.listwidget.active_list
        files = active_list.get_items()

        if not search:
            active_list.setUpdatesEnabled(False)
            for item in files:
                item.setHidden(False)

            active_list.post_filter()
            active_list.setUpdatesEnabled(True)
            active_list.filter = None
            return

        self._filter_list(active_list, search, invert, use_regex, re_filter)

        existing_searches = {self.search.itemText(x) for x in range(self.search.count())}
        if search not in existing_searches:
            self.search.addItem(search)
            if self.search.count() > SEARCH_HISTORY_MAX:
                self.search.removeItem(0)

    def filter_list(
        self: "MainWindow",
        file_list: FileViewAbstract,
        search: str,
        invert: bool,
        use_regex: bool,
        re_filter: bool,
    ):
        self._filter_list(file_list, search, invert, use_regex, re_filter)

    def _filter_list(
        self: "MainWindow",
        file_list: FileViewAbstract,
        search: str,
        invert: bool,
        use_regex: bool,
        re_filter: bool,
    ):
        files = file_list.get_items()

        if use_regex:
            try:
                pattern = re.compile(search, re.IGNORECASE)
                matcher = pattern.search
            except re.error:
                return
        else:
            from functools import partial

            matcher = partial(fnmatch.fnmatch, pat=f"*{search.lower()}*")

        file_list.setUpdatesEnabled(False)
        for item in files:
            if item.isHidden() and re_filter:
                continue

            item_text = file_list.get_item_path(item)
            if item_text is None or item_text == "":
                continue

            match_text = item_text if use_regex else item_text.lower()
            match = bool(matcher(match_text))
            item.setHidden(not (match ^ invert))

        file_list.post_filter()
        file_list.setUpdatesEnabled(True)
        file_list.filter = (search, invert, use_regex)
