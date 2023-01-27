
SEARCH_HISTORY_MAX = 15
HELP_STRING = """
<h2>Shortcuts</h2>
<ul>
    {shortcuts}
</ul> 

<h2> File Search </h2>
File search is based on Unix filename pattern. This means that something like 
"sauron.ini" will look for a file called exactly "sauron.ini". If you're looking for
something like "data/ini/objects/sauron.ini" make sure you add a * to match everything
before. Like "*/sauron.ini".<br/>
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
Suggestions and bug reports should also go there. <br/><br/>

Version: <b>{version}</b>
"""

def normalize_name(name : str):
    return name.replace("/", "\\")

def decode_string(text : bytes):
    return text.decode("Latin-1")

def encode_string(text : str):
    return text.encode("Latin-1")

def preview_name(name : str):
    return f"PREVIEW - {name}"

def is_preview(name : str):
    return name.startswith("PREVIEW - ")

def unsaved_name(name : str):
    return f"{name} *"

def is_unsaved(name : str):
    return name.endswith(" *")
