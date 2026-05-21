import os
from urllib.parse import quote

from PyQt6.QtGui import QColor, QPalette

from utils.utils import resource_path

_GLYPH_NAMES = (
    "chevron_right",
    "chevron_down",
    "vline",
    "branch_more",
    "branch_end",
    "combobox_arrow",
)


def _load_glyphs() -> dict:
    glyphs = {}
    for name in _GLYPH_NAMES:
        path = resource_path(os.path.join("theme", f"{name}.svg"))
        try:
            with open(path, "r", encoding="utf-8") as f:
                glyphs[name] = f.read()
        except OSError:
            glyphs[name] = ""
    return glyphs


_GLYPHS = _load_glyphs()


def _data_uri(svg_text: str, color: str) -> str:
    tinted = svg_text.replace("currentColor", color)
    return "data:image/svg+xml;utf8," + quote(tinted, safe="")

NORD = {
    "is_dark": True,
    "window": "#2E3440",
    "window_text": "#D8DEE9",
    "base": "#3B4252",
    "alt_base": "#434C5E",
    "text": "#ECEFF4",
    "button": "#3B4252",
    "button_text": "#ECEFF4",
    "bright_text": "#BF616A",
    "highlight": "#5E81AC",
    "highlight_text": "#ECEFF4",
    "link": "#88C0D0",
    "disabled_text": "#4C566A",
    "tooltip_base": "#434C5E",
    "tooltip_text": "#ECEFF4",
    "border": "#4C566A",
    "menu_hover": "#434C5E",
    "scrollbar": "#4C566A",
}

SOLARIZED_DARK = {
    "is_dark": True,
    "window": "#002B36",
    "window_text": "#93A1A1",
    "base": "#073642",
    "alt_base": "#002B36",
    "text": "#EEE8D5",
    "button": "#073642",
    "button_text": "#93A1A1",
    "bright_text": "#DC322F",
    "highlight": "#268BD2",
    "highlight_text": "#FDF6E3",
    "link": "#2AA198",
    "disabled_text": "#586E75",
    "tooltip_base": "#073642",
    "tooltip_text": "#EEE8D5",
    "border": "#586E75",
    "menu_hover": "#073642",
    "scrollbar": "#586E75",
}

SOLARIZED_LIGHT = {
    "is_dark": False,
    "window": "#FDF6E3",
    "window_text": "#586E75",
    "base": "#EEE8D5",
    "alt_base": "#FDF6E3",
    "text": "#073642",
    "button": "#EEE8D5",
    "button_text": "#586E75",
    "bright_text": "#DC322F",
    "highlight": "#268BD2",
    "highlight_text": "#FDF6E3",
    "link": "#2AA198",
    "disabled_text": "#93A1A1",
    "tooltip_base": "#EEE8D5",
    "tooltip_text": "#073642",
    "border": "#93A1A1",
    "menu_hover": "#EEE8D5",
    "scrollbar": "#93A1A1",
}

DRACULA = {
    "is_dark": True,
    "window": "#282A36",
    "window_text": "#F8F8F2",
    "base": "#21222C",
    "alt_base": "#282A36",
    "text": "#F8F8F2",
    "button": "#44475A",
    "button_text": "#F8F8F2",
    "bright_text": "#FF5555",
    "highlight": "#BD93F9",
    "highlight_text": "#282A36",
    "link": "#8BE9FD",
    "disabled_text": "#6272A4",
    "tooltip_base": "#44475A",
    "tooltip_text": "#F8F8F2",
    "border": "#44475A",
    "menu_hover": "#44475A",
    "scrollbar": "#44475A",
}

GRUVBOX_DARK = {
    "is_dark": True,
    "window": "#282828",
    "window_text": "#EBDBB2",
    "base": "#3C3836",
    "alt_base": "#32302F",
    "text": "#EBDBB2",
    "button": "#3C3836",
    "button_text": "#EBDBB2",
    "bright_text": "#FB4934",
    "highlight": "#458588",
    "highlight_text": "#FBF1C7",
    "link": "#83A598",
    "disabled_text": "#7C6F64",
    "tooltip_base": "#3C3836",
    "tooltip_text": "#EBDBB2",
    "border": "#504945",
    "menu_hover": "#504945",
    "scrollbar": "#504945",
}

PALETTE_THEMES = {
    "nord": ("Nord", NORD),
    "solarized_dark": ("Solarized Dark", SOLARIZED_DARK),
    "solarized_light": ("Solarized Light", SOLARIZED_LIGHT),
    "dracula": ("Dracula", DRACULA),
    "gruvbox_dark": ("Gruvbox Dark", GRUVBOX_DARK),
}


def _c(hex_str: str) -> QColor:
    return QColor(hex_str)


def build_palette(scheme: dict) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    p.setColor(role.Window, _c(scheme["window"]))
    p.setColor(role.WindowText, _c(scheme["window_text"]))
    p.setColor(role.Base, _c(scheme["base"]))
    p.setColor(role.AlternateBase, _c(scheme["alt_base"]))
    p.setColor(role.Text, _c(scheme["text"]))
    p.setColor(role.Button, _c(scheme["button"]))
    p.setColor(role.ButtonText, _c(scheme["button_text"]))
    p.setColor(role.BrightText, _c(scheme["bright_text"]))
    p.setColor(role.Highlight, _c(scheme["highlight"]))
    p.setColor(role.HighlightedText, _c(scheme["highlight_text"]))
    p.setColor(role.Link, _c(scheme["link"]))
    p.setColor(role.ToolTipBase, _c(scheme["tooltip_base"]))
    p.setColor(role.ToolTipText, _c(scheme["tooltip_text"]))
    p.setColor(role.PlaceholderText, _c(scheme["disabled_text"]))

    disabled = _c(scheme["disabled_text"])
    p.setColor(group.Disabled, role.Text, disabled)
    p.setColor(group.Disabled, role.WindowText, disabled)
    p.setColor(group.Disabled, role.ButtonText, disabled)
    p.setColor(group.Disabled, role.HighlightedText, disabled)

    return p


def build_stylesheet(scheme: dict) -> str:
    s = scheme
    fg = s["text"]
    line = s["border"]
    chevron_right = _data_uri(_GLYPHS["chevron_right"], fg)
    chevron_down = _data_uri(_GLYPHS["chevron_down"], fg)
    vline = _data_uri(_GLYPHS["vline"], line)
    branch_more = _data_uri(_GLYPHS["branch_more"], line)
    branch_end = _data_uri(_GLYPHS["branch_end"], line)
    combobox_arrow = _data_uri(_GLYPHS["combobox_arrow"], fg)
    return f"""
    QMainWindow, QDialog {{
        background-color: {s['window']};
        color: {s['window_text']};
    }}
    QToolTip {{
        color: {s['tooltip_text']};
        background-color: {s['tooltip_base']};
        border: 1px solid {s['border']};
    }}
    QMenu {{
        background-color: {s['base']};
        color: {s['text']};
        border: 1px solid {s['border']};
    }}
    QMenu::item:selected {{
        background-color: {s['menu_hover']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {s['border']};
        margin: 4px 0;
    }}
    QMenuBar {{
        background-color: {s['window']};
        color: {s['window_text']};
    }}
    QMenuBar::item:selected {{
        background-color: {s['menu_hover']};
    }}
    QTabWidget::pane {{
        border: 1px solid {s['border']};
    }}
    QTabBar::tab {{
        background: {s['base']};
        color: {s['text']};
        padding: 5px 10px;
        border: 1px solid {s['border']};
    }}
    QTabBar::tab:selected {{
        background: {s['alt_base']};
    }}
    QTabBar::tab:hover {{
        background: {s['menu_hover']};
    }}
    QTabBar::tab:disabled {{
        color: {s['disabled_text']};
    }}
    QTreeView, QTreeWidget, QListView, QListWidget {{
        background-color: {s['base']};
        alternate-background-color: {s['alt_base']};
        color: {s['text']};
        border: 1px solid {s['border']};
        outline: 0;
    }}
    QTreeView::item, QTreeWidget::item, QListView::item, QListWidget::item {{
        color: {s['text']};
        padding: 2px;
    }}
    QTreeView::item:hover, QTreeWidget::item:hover, QListView::item:hover, QListWidget::item:hover {{
        background-color: {s['menu_hover']};
    }}
    QTreeView::item:selected, QTreeWidget::item:selected, QListView::item:selected, QListWidget::item:selected {{
        background-color: {s['highlight']};
        color: {s['highlight_text']};
    }}
    QTreeView::item:selected:!active, QTreeWidget::item:selected:!active,
    QListView::item:selected:!active, QListWidget::item:selected:!active {{
        background-color: {s['highlight']};
        color: {s['highlight_text']};
    }}
    QTreeView::branch {{
        background-color: {s['base']};
    }}
    QTreeView::branch:hover {{
        background-color: {s['menu_hover']};
    }}
    QTreeView::branch:selected {{
        background-color: {s['highlight']};
    }}
    QTreeView::branch:has-siblings:!adjoins-item {{
        border-image: none;
        image: url({vline});
    }}
    QTreeView::branch:has-siblings:adjoins-item {{
        border-image: none;
        image: url({branch_more});
    }}
    QTreeView::branch:!has-children:!has-siblings:adjoins-item {{
        border-image: none;
        image: url({branch_end});
    }}
    QTreeView::branch:has-children:!has-siblings:closed,
    QTreeView::branch:has-children:has-siblings:closed {{
        border-image: none;
        image: url({chevron_right});
    }}
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {{
        border-image: none;
        image: url({chevron_down});
    }}
    QScrollBar:vertical {{
        background: {s['base']};
        width: 12px;
        border: none;
        margin: 0;
    }}
    QScrollBar:horizontal {{
        background: {s['base']};
        height: 12px;
        border: none;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {s['scrollbar']};
        border-radius: 3px;
        min-height: 20px;
    }}
    QScrollBar::handle:horizontal {{
        background: {s['scrollbar']};
        border-radius: 3px;
        min-width: 20px;
    }}
    QScrollBar::handle:hover {{
        background: {s['highlight']};
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: {s['base']};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        background: none;
        border: none;
        width: 0;
        height: 0;
    }}
    QScrollBar::up-arrow, QScrollBar::down-arrow,
    QScrollBar::left-arrow, QScrollBar::right-arrow {{
        background: none;
        border: none;
        width: 0;
        height: 0;
    }}
    QHeaderView::section {{
        background-color: {s['base']};
        color: {s['text']};
        padding: 4px;
        border: 1px solid {s['border']};
    }}
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
        background-color: {s['base']};
        color: {s['text']};
        border: 1px solid {s['border']};
        selection-background-color: {s['highlight']};
        selection-color: {s['highlight_text']};
    }}
    QComboBox:focus, QComboBox:on {{
        border: 1px solid {s['highlight']};
    }}
    QComboBox::drop-down {{
        border: none;
        background: {s['base']};
        width: 16px;
    }}
    QComboBox::down-arrow {{
        image: url({combobox_arrow});
        width: 10px;
        height: 10px;
    }}
    QComboBox::down-arrow:on {{
        image: url({chevron_down});
    }}
    QComboBox QAbstractItemView {{
        background-color: {s['base']};
        color: {s['text']};
        border: 1px solid {s['border']};
        selection-background-color: {s['highlight']};
        selection-color: {s['highlight_text']};
        outline: 0;
        padding: 2px;
    }}
    QCheckBox {{
        color: {s['text']};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {s['border']};
        background-color: {s['base']};
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {s['highlight']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {s['highlight']};
        border: 1px solid {s['highlight']};
    }}
    QCheckBox::indicator:disabled {{
        background-color: {s['alt_base']};
        border: 1px solid {s['disabled_text']};
    }}
    QPushButton, QToolButton {{
        background-color: {s['button']};
        color: {s['button_text']};
        border: 1px solid {s['border']};
        padding: 4px 10px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: {s['menu_hover']};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background-color: {s['highlight']};
        color: {s['highlight_text']};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        color: {s['disabled_text']};
    }}
    QSplitter::handle {{
        background-color: {s['border']};
    }}
    QSplitter::handle:hover {{
        background-color: {s['highlight']};
    }}
    QStatusBar {{
        background-color: {s['window']};
        color: {s['window_text']};
    }}
    QGroupBox {{
        border: 1px solid {s['border']};
        margin-top: 8px;
    }}
    QGroupBox::title {{
        color: {s['text']};
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    """
