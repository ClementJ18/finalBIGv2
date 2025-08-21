import os
import sys

SEARCH_HISTORY_MAX = 20
RECENT_FILES_MAX = 10
HELP_STRING = """
<h2>Shortcuts</h2>
<ul>
    {shortcuts}
</ul> 

<h2> File Search </h2>
File search is based on Unix filename pattern. This means that something like 
"sauron.ini" will look for a file called exactly "sauron.ini". If you're looking for
something like "data\ini\objects\sauron.ini" make sure you add a * to match everything
before. Like "*\sauron.ini".<br/>
<br/>
Quick rundown
<ul>
<li><b> * </b> - matches everything </li>
<li><b> ? </b> - matches any single character </li>
<li><b> [seq] </b> - matches any character in seq </li>
<li><b> [!seq] </b> - matches any character not in seq </li>
</ul>
"""

ABOUT_STRING = """
<h2>About</h2>
<b>FinalBIGv2</b> was made by officialNecro because he was getting very annoyed at
FinalBIG crashing all the time. It's not perfect either but it works on his machine and
maybe it'll work on other people's machines.<br/>

Source code is available <a href="https://github.com/ClementJ18/finalBIGv2">here</a>. 
Suggestions and bug reports should also go there. 
Updated by Tria For C&C Generals (BIGF support) & Additional Changes.<br/><br/>

Version: <b>{version}</b>
"""


def normalize_name(name: str):
    if name is None:
        return ""

    return name.replace("/", "\\")


def decode_string(text: bytes, encoding: str):
    return text.decode(encoding)


def encode_string(text: str, encoding: str):
    return text.encode(encoding)


def preview_name(name: str):
    return f"PREVIEW - {name}"


def is_preview(name: str):
    return name.startswith("PREVIEW - ")


def unsaved_name(name: str):
    return f"{name} *"


def is_unsaved(name: str):
    return name.endswith(" *")


def str_to_bool(value):
    return bool(int(value))


def human_readable_size(size: int, decimal_places: int = 2) -> str:
    """Convert bytes to a human-readable format (KB, MB, GB...)."""
    if size < 0:
        raise ValueError("Size must be non-negative")

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    size = float(size)

    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    return f"{size:.{decimal_places}f} {units[index]}"


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath("./src")
    return os.path.join(base_path, "assets", relative_path)


ENCODING_LIST = [
    "ascii",
    "big5",
    "big5hkscs",
    "cp037",
    "cp273",
    "cp424",
    "cp437",
    "cp500",
    "cp720",
    "cp737",
    "cp775",
    "cp850",
    "cp852",
    "cp855",
    "cp856",
    "cp857",
    "cp858",
    "cp860",
    "cp861",
    "cp862",
    "cp863",
    "cp864",
    "cp865",
    "cp866",
    "cp869",
    "cp874",
    "cp875",
    "cp932",
    "cp949",
    "cp950",
    "cp1006",
    "cp1026",
    "cp1125",
    "cp1140",
    "cp1250",
    "cp1251",
    "cp1252",
    "cp1253",
    "cp1254",
    "cp1255",
    "cp1256",
    "cp1257",
    "cp1258",
    "euc_jp",
    "euc_jis_2004",
    "euc_jisx0213",
    "euc_kr",
    "gb2312",
    "gbk",
    "gb18030",
    "hz",
    "iso2022_jp",
    "iso2022_jp_1",
    "iso2022_jp_2",
    "iso2022_jp_2004",
    "iso2022_jp_3",
    "iso2022_jp_ext",
    "iso2022_kr",
    "latin_1",
    "iso8859_2",
    "iso8859_3",
    "iso8859_4",
    "iso8859_5",
    "iso8859_6",
    "iso8859_7",
    "iso8859_8",
    "iso8859_9",
    "iso8859_10",
    "iso8859_11",
    "iso8859_13",
    "iso8859_14",
    "iso8859_15",
    "iso8859_16",
    "johab",
    "koi8_r",
    "koi8_t",
    "koi8_u",
    "kz1048",
    "mac_cyrillic",
    "mac_greek",
    "mac_iceland",
    "mac_latin2",
    "mac_roman",
    "mac_turkish",
    "ptcp154",
    "shift_jis",
    "shift_jis_2004",
    "shift_jisx0213",
    "utf_32",
    "utf_32_be",
    "utf_32_le",
    "utf_16",
    "utf_16_be",
    "utf_16_le",
    "utf_7",
    "utf_8",
    "utf_8_sig",
]
