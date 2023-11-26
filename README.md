# FinalBIGv2

A PyQt GUI intended to supplant the outdated FinalBIG program in the manipulating of .big archives. FinalBIGv2 can do all the things FinalBIG can and more! It has the following additional features:

* Read support for more than just text files including:
    * Music files (currently disabled)
    * CAH files
    * Maps and Base files including editing!
* Smoother navigation
* Open source
* Syntax Highlighting
* Filtering by filename
* Text search in individual files (including with Regex)
* Text search the entire BIG file
* Adapts to dark mode
* Linux support
* Select multiple files at once from the list with shift, ctrl or just by dragging
* Rename files in place
* Right click menu for ease of access in the file list
* User settings for persistent customisation
* Open files in your default applications or use the internal editor
* Auto-compile by Github
* Scroll through multiple instances of the file list
* And many more in the future!

At this very early stage I am mostly looking for feedback so if you have any thoughts feel free to open a ticket or find me on discord @Necro#6714. I can usually be found on quite a few BFME/SAGE servers.

![Demo of the GUI](resources/demo_light.png)
![Demo of the GUI](resources/demo_dark.png)


## How to use
A new build is compiled directly from the source everytime a commit is pushed to the repository, you can download it from the [build menu](https://github.com/ClementJ18/finalBIGv2/actions/workflows/main.yml?query=branch%3Amain).

There is also a public download that's semi-regularly updated in case you don't have a GitHub account: https://www.moddb.com/downloads/finalbigv2

### Running the repository
Don't trust the exe or it doesn't work? No problem
1. Download and install python: https://www.python.org/downloads/release/python-31011/
2. Download the repository as a zip and extract it to a folder
3. Open a terminal and navigate to the folder with `cd PATH` where PATH is the path of the folder
3. Install the dependencies with `python -m pip install -r requirements.txt`
4. Run the application with `python src/main.py`

## Current Limitations
* Syntax Highlighting gets kinda weird with non-ASCII characters, you can reset it by turning it off and on
* Audio files are currently not supported until I find a way to bundle ffmpeg
* The LUA and XML editor don't switch to dark mode
* Line number color of currently open editors does not adapt properly when switching dark/light mode (fix by re-opening tabs)

## Demo
Search entire archive for text

![Search text in archive](resources/search_archive_demo.gif)

