import os
from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from misc import FileList, FileListTabs, TabWidget

if TYPE_CHECKING:
    from main import MainWindow


class HasUiElements:
    listwidget: FileListTabs
    tabs: TabWidget
    search: QComboBox
    search_button: QPushButton
    invert_box: QCheckBox
    re_filter_box: QCheckBox
    regex_filter_box: QCheckBox
    splitter: QSplitter
    shortcuts: list
    recent_menu: QMenu
    dark_mode_action: QAction
    use_external_action: QAction
    large_archive_action: QAction
    preview_action: QAction
    lock_exceptions: list


def create_ui(main: "MainWindow", basedir: str):
    main.setAcceptDrops(True)
    layout = QVBoxLayout()

    main.listwidget = FileListTabs(main)
    main.listwidget.setElideMode(Qt.TextElideMode.ElideLeft)
    main.listwidget.setTabsClosable(True)
    main.listwidget.setUsesScrollButtons(True)
    main.listwidget.addTab(FileList(main), QIcon(os.path.join(basedir, "new_tab.png")), "")
    main.listwidget.tabBar().setTabButton(
        0, main.listwidget.tabBar().ButtonPosition.RightSide, None
    )

    main.listwidget.currentChanged.connect(main.open_new_tab)
    main.listwidget.tabCloseRequested.connect(main.remove_list_tab)

    search_widget = QWidget(main)
    search_layout = QHBoxLayout()
    layout.addWidget(search_widget, stretch=1)
    search_widget.setLayout(search_layout)

    main.search = QComboBox(main)
    main.search.setEditable(True)
    completer = main.search.completer()
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
    main.search.setCompleter(completer)
    search_layout.addWidget(main.search, stretch=5)

    main.search_button = QPushButton("Filter file list", main)
    main.search_button.clicked.connect(main.filter_list)
    search_layout.addWidget(main.search_button, stretch=1)

    main.invert_box = QCheckBox("Invert?", main)
    main.invert_box.setToolTip("Filter based on names that do <b>NOT</b> match?")
    search_layout.addWidget(main.invert_box)

    main.re_filter_box = QCheckBox("Re-filter?", main)
    main.re_filter_box.setToolTip(
        "Apply the new filter on the current list rather than clearing previous filters"
    )
    search_layout.addWidget(main.re_filter_box)

    main.regex_filter_box = QCheckBox("Regex?", main)
    search_layout.addWidget(main.regex_filter_box)

    main.tabs = TabWidget(main)
    main.tabs.setElideMode(Qt.TextElideMode.ElideLeft)
    main.tabs.setTabsClosable(True)
    main.tabs.tabCloseRequested.connect(main.close_tab)
    main.tabs.setUsesScrollButtons(True)
    main.tabs.tabBar().installEventFilter(main)

    splitter = QSplitter(Qt.Orientation.Horizontal, main)
    splitter.setOrientation(Qt.Orientation.Horizontal)
    splitter.addWidget(main.listwidget)
    splitter.addWidget(main.tabs)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 200)
    layout.addWidget(splitter, stretch=100)

    widget = QWidget()
    widget.setLayout(layout)
    main.setCentralWidget(widget)


def create_shortcuts(main: "MainWindow"):
    main.shortcuts = [
        ("Click on file", "Preview file"),
        ("Double-click on file", "Edit file"),
        ("Left-click drag", "Select multiple files"),
        ("Right-click on file/selection", "Context menu"),
        (
            QShortcut(
                QKeySequence("CTRL+N"),
                main,
                main.new,
            ),
            "Create a new archive",
        ),
        (
            QShortcut(QKeySequence("CTRL+O"), main, main.open),
            "Open a different archive",
        ),
        (QShortcut(QKeySequence("CTRL+S"), main, main.save), "Save the archive"),
        (
            QShortcut(QKeySequence("CTRL+SHIFT+S"), main, main.save_editor),
            "Save the current text editor",
        ),
        (
            QShortcut(QKeySequence("CTRL+RETURN"), main, main.filter_list),
            "Filter the list with the current search",
        ),
        (
            QShortcut(QKeySequence("CTRL+F"), main, main.search_file),
            "Search the current text editor",
        ),
        (
            QShortcut(QKeySequence("CTRL+W"), main, main.close_tab_shortcut),
            "Close the current tab",
        ),
        (
            "CTRL+;",
            "Comment/uncomment the currently selected text",
        ),
        (
            QShortcut(QKeySequence("CTRL+H"), main, main.show_help),
            "Show the help",
        ),
        (
            QShortcut(
                QKeySequence("CTRL+SHIFT+F"),
                main,
                lambda: main.search_archive(main.settings.search_archive_regex_bool),
            ),
            "Search for text in the archive",
        ),
        (
            QShortcut(QKeySequence("ALT+R"), main, main.settings.toggle_search_archive_regex),
            "Toggle the 'Search for text in archive' shortcut regex search on/off",
        ),
        ("Arrow keys", "Rotate a model in a w3d tab"),
        ("Mouse wheel", "Zoom a model in and out in a w3d tab"),
        ("Mouse drag", "Rotate a model in a w3d tab"),
    ]


def create_menu(main: "MainWindow"):
    menu = main.menuBar()
    file_menu = menu.addMenu("&File")
    main.lock_exceptions.append(file_menu.addAction("New", main.new))
    main.lock_exceptions.append(file_menu.addAction("Open", main.open))
    file_menu.addAction("Close", main.close_archive)
    file_menu.addAction("Save", main.save)
    file_menu.addAction("Save as...", main.save_as)
    main.recent_menu = QMenu("Open Recent", main)
    file_menu.addMenu(main.recent_menu)
    main.update_recent_files_menu()

    edit_menu = menu.addMenu("&Edit")
    edit_menu.addAction("New file", main.new_file)
    edit_menu.addAction("Add file", main.add_file)
    edit_menu.addAction("Add directory", main.add_folder)
    edit_menu.addAction("Delete selection", main.delete)
    edit_menu.addAction("Rename file", main.rename)

    edit_menu.addSeparator()

    edit_menu.addAction("Extract selection", main.extract)
    edit_menu.addAction("Extract all", main.extract_all)
    edit_menu.addAction("Extract filtered", main.extract_filtered)

    tools_menu = menu.addMenu("&Tools")
    tools_menu.addAction("Dump entire file list", lambda: main.dump_list(False))
    tools_menu.addAction("Dump filtered file list", lambda: main.dump_list(True))
    tools_menu.addAction("Merge another archive", main.merge_archives)

    tools_menu.addSeparator()

    tools_menu.addAction("Copy file name", main.copy_name)

    tools_menu.addSeparator()

    tools_menu.addAction("Find text in archive", lambda: main.search_archive(False))
    tools_menu.addAction("Find text in archive (REGEX)", lambda: main.search_archive(True))

    option_menu = menu.addMenu("&Help")
    option_menu.addAction("About", main.show_about)
    option_menu.addAction("Help", main.show_help)

    option_menu.addSeparator()

    main.dark_mode_action = QAction("Dark Mode?", main, checkable=True)
    main.dark_mode_action.setToolTip("Whether to use dark mode or not")
    main.dark_mode_action.setChecked(main.settings.dark_mode)
    main.dark_mode_action.triggered.connect(main.settings.toggle_dark_mode)
    option_menu.addAction(main.dark_mode_action)

    main.use_external_action = QAction("Use external programs?", main, checkable=True)
    main.use_external_action.setToolTip(
        "Whether to open using the internal editor or the user's default application"
    )
    main.use_external_action.setChecked(main.settings.external)
    main.use_external_action.triggered.connect(main.settings.toggle_external)
    option_menu.addAction(main.use_external_action)

    main.large_archive_action = QAction("Use Large Archive Architecture?", main, checkable=True)
    main.large_archive_action.setToolTip(
        "Change the system to use Large Archives, a slower system that handles large files better"
    )
    main.large_archive_action.setChecked(main.settings.large_archive)
    main.large_archive_action.triggered.connect(main.settings.toggle_large_archives)
    option_menu.addAction(main.large_archive_action)

    main.preview_action = QAction("Preview?", main, checkable=True)
    main.preview_action.setToolTip("Enable previewing files")
    main.preview_action.setChecked(main.settings.preview_enabled)
    main.preview_action.triggered.connect(main.settings.toggle_preview)
    option_menu.addAction(main.preview_action)

    option_menu.addAction("Set encoding", main.settings.set_encoding)


def generate_ui(main: "MainWindow", basedir: str):
    create_ui(main, basedir)
    create_shortcuts(main)
    create_menu(main)
