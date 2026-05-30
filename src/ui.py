from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QKeySequence
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

from file_views import FileViewTabs, ListFileView
from misc import SearchBox, TabWidget
from utils.utils import resource_path

if TYPE_CHECKING:
    from main import MainWindow


class HasUiElements:
    listwidget: FileViewTabs
    tabs: TabWidget
    search: QComboBox
    search_button: QPushButton
    invert_box: QCheckBox
    re_filter_box: QCheckBox
    regex_filter_box: QCheckBox
    splitter: QSplitter
    shortcuts: list
    recent_menu: QMenu
    workspace_menu: QMenu
    undo_action: QAction
    redo_action: QAction
    lock_exceptions: list


def create_ui(main: "MainWindow"):
    main.setAcceptDrops(True)
    layout = QVBoxLayout()

    main.listwidget = FileViewTabs(main)
    main.listwidget.setElideMode(Qt.TextElideMode.ElideLeft)
    main.listwidget.setTabsClosable(True)
    main.listwidget.setUsesScrollButtons(True)
    main.listwidget.addTab(ListFileView(main), QIcon(resource_path("new_tab.png")), "")
    main.listwidget.tabBar().setTabButton(
        0, main.listwidget.tabBar().ButtonPosition.RightSide, None
    )

    main.listwidget.currentChanged.connect(main.open_new_tab)
    main.listwidget.tabCloseRequested.connect(main.remove_list_tab)

    search_widget = QWidget(main)
    search_layout = QHBoxLayout()
    layout.addWidget(search_widget, stretch=1)
    search_widget.setLayout(search_layout)

    main.search = SearchBox(
        main, enter_callback=main.filter_list_from_search, placeholder_text="Search file list..."
    )
    completer = main.search.completer()
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
    main.search.setCompleter(completer)
    search_layout.addWidget(main.search, stretch=5)

    main.search_button = QPushButton("Filter file list", main)
    main.search_button.clicked.connect(main.filter_list_from_search)
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

    main.splitter = QSplitter(Qt.Orientation.Horizontal, main)
    main.splitter.setOrientation(Qt.Orientation.Horizontal)
    main.splitter.addWidget(main.listwidget)
    main.splitter.addWidget(main.tabs)
    main.splitter.setStretchFactor(0, 1)
    main.splitter.setStretchFactor(1, 200)
    layout.addWidget(main.splitter, stretch=100)

    widget = QWidget()
    widget.setLayout(layout)
    main.setCentralWidget(widget)


def create_menu(main: "MainWindow"):
    menu = main.menuBar()
    file_menu = menu.addMenu("&File")
    new_archive_action = file_menu.addAction("&New", main.new)
    new_archive_action.setShortcut(QKeySequence("CTRL+N"))
    main.lock_exceptions.append(new_archive_action)

    open_archive_action = file_menu.addAction("&Open", main.open)
    open_archive_action.setShortcut(QKeySequence("CTRL+O"))
    main.lock_exceptions.append(open_archive_action)

    close_archive_action = file_menu.addAction("&Close", main.close_archive)
    close_archive_action.setShortcut(QKeySequence("CTRL+SHIFT+W"))

    save_archive_action = file_menu.addAction("&Save", main.save)
    save_archive_action.setShortcut(QKeySequence("CTRL+S"))

    file_menu.addAction("Save &As...", main.save_as)

    file_menu.addSeparator()
    settings_action = file_menu.addAction("&Settings...", main.show_settings)
    settings_action.setShortcut(QKeySequence("CTRL+,"))
    main.lock_exceptions.append(settings_action)
    file_menu.addSeparator()

    main.recent_menu = QMenu("Open &Recent", main)
    file_menu.addMenu(main.recent_menu)
    main.update_recent_files_menu()

    main.workspace_menu = QMenu("Workspaces", main)
    file_menu.addMenu(main.workspace_menu)
    main.lock_exceptions.append(main.workspace_menu)

    main.workspace_menu.addAction("Save Workspace", main.save_workspace)

    open_workspace_action = main.workspace_menu.addAction(
        "Manage Workspaces", main.manage_workspace
    )
    open_workspace_action.setShortcut(QKeySequence("CTRL+R"))
    main.lock_exceptions.append(open_workspace_action)

    main.workspace_menu.addAction("Close Workspace", main.close_workspace)

    main.workspace_menu.addSeparator()
    main.update_recent_workspace_menu()

    edit_menu = menu.addMenu("&Edit")
    main.undo_action = edit_menu.addAction("&Undo", main.undo_archive)
    main.undo_action.setShortcut(QKeySequence("CTRL+Z"))
    main.undo_action.setEnabled(False)

    main.redo_action = edit_menu.addAction("Re&do", main.redo_archive)
    main.redo_action.setShortcut(QKeySequence("CTRL+Y"))
    main.redo_action.setEnabled(False)

    edit_menu.addSeparator()

    new_file_action = edit_menu.addAction("&New File", main.new_file)
    new_file_action.setShortcut(QKeySequence("CTRL+SHIFT+N"))

    add_file_action = edit_menu.addAction("Add &File", main.add_file)
    add_file_action.setShortcut(QKeySequence("CTRL+SHIFT+A"))

    add_folder_action = edit_menu.addAction("&Add Directory", main.add_folder)
    add_folder_action.setShortcut(QKeySequence("CTRL+SHIFT+O"))

    delete_files_action = edit_menu.addAction("&Delete Selection", main.delete)
    delete_files_action.setShortcut(QKeySequence("CTRL+SHIFT+D"))

    rename_file_action = edit_menu.addAction("&Rename File", main.rename)
    rename_file_action.setShortcut(QKeySequence("CTRL+SHIFT+R"))

    save_current_editor_action = edit_menu.addAction("&Save current tab", main.save_editor)
    save_current_editor_action.setShortcut(QKeySequence("CTRL+SHIFT+S"))

    save_all_editors_action = edit_menu.addAction("Save all &tabs", main.save_all_editors)
    save_all_editors_action.setShortcut(QKeySequence("ALT+SHIFT+S"))

    close_editor_action = edit_menu.addAction("&Close current tab", main.close_tab_shortcut)
    close_editor_action.setShortcut(QKeySequence("CTRL+W"))

    edit_menu.addSeparator()

    edit_menu.addAction("&Extract Selection", main.extract)
    edit_menu.addAction("Extract &All", main.extract_all)
    edit_menu.addAction("Extract &Filtered", main.extract_filtered)

    tools_menu = menu.addMenu("&Tools")
    tools_menu.addAction("Dump &Entire file list", lambda: main.dump_list(False))
    tools_menu.addAction("Dump &Filtered file list", lambda: main.dump_list(True))
    tools_menu.addAction("Merge &Another archive", main.merge_archives)

    tools_menu.addSeparator()

    tools_menu.addAction("&Copy file name", main.copy_name)

    tools_menu.addSeparator()

    search_archive_action = tools_menu.addAction(
        "&Find text in archive", lambda: main.search_archive(False)
    )
    search_archive_action.setShortcut(QKeySequence("CTRL+SHIFT+F"))

    search_achive_regex_action = tools_menu.addAction(
        "Find text in archive (&REGEX)", lambda: main.search_archive(True)
    )
    search_achive_regex_action.setShortcut(QKeySequence("ALT+SHIFT+F"))

    option_menu = menu.addMenu("&Help")
    main.lock_exceptions.append(option_menu.addAction("&About", main.show_about))

    help_action = option_menu.addAction("&Help", main.show_help)
    help_action.setShortcut(QKeySequence("CTRL+H"))
    main.lock_exceptions.append(help_action)


def generate_ui(main: "MainWindow"):
    create_ui(main)
    create_menu(main)
