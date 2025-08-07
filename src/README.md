# pyBIG
Python library to programatically manipulate .big files, the archive format used in many of the game titles created by Westwood studios.

This library is largely possible due to the work done by the OpenSage team ([Link](https://github.com/OpenSAGE/Docs/blob/master/file-formats/big/index.rst)). Essentially this library is a python wrapper around the knowledge they gathered with some helper functions.

## Installation

You can get it from Pypi: https://pypi.org/project/pyBIG/

```
pip install pyBIG
```

## Usage
The library is based on the pyBIG.Archive object. This objects takes raw bytes representing a BIG archive. The decision to take raw bytes allow the user to decide where those bytes come from, whether a file stored in memory or on disk. There is also a class method, Archive.from_directory that allows you to load a directory on the disk painlessly.

You can modify the archive in memory with the following methods:
 - Archive.edit_file(str, bytes)
 - Archive.add_file(str, bytes)
 - Archive.remove_file(str)

Each method takes a name which is the windows-format path to the file in the archive so something like 'data\ini\weapon.ini'. The methods that takes bytes represent the new contents of the file as bytes.

It is important to note that these methods do not actually modify the archive but it is as if. This does not update the entries or the raw bytes. If you want to update the archive you need to call Archive.repack(). This is an expensive operation which is only called automatically when the archive is saved or extracted. The rest is up to the user.

You can look at the tests for more examples.

```python
from pyBIG import Archive

with open("test.big", "rb") as f:
    archive = Archive(f.read())

# get the contents of a file as bytes
contents = archive.read_file("data\\ini\\weapon.ini")

#add a new file
archive.add_file("data\\ini\john.ini", b"this is the story of a man named john")
archive.repack()

#remove a file
archive.remove_file("data\\ini\\john.ini")
archive.repack()

#save the big file back to disk, this will also take care of repacking
# the file with the latest modified entries
archive.save("test.big")

# extract all the files in the archive
archive.extract("output/")

# load an archive from a directory
archive = Archive.from_directory("output/")

```

### Advanced
In version 0.2.0, this library also makes the `LargeArchive` object available. This special object does not store the entire file into memory, allowing for manipulation of large files. It works essentially the same except that reading is done from the file present on disk and functions are tied to that location. Repacking does the same as save on this object but it is recommended to instead use the save function.

It is important to note that adding and editing files in a LargeArchive stores them in memory. As such it is recommended to to save at regular interval to commit these changes to disk. The LargeArchive object exposes `archive_memory_size` as a simple way of seeing how many bytes are currently stored directly on the object. 

```python
from pyBIG import LargeArchive

archive = LargeArchive("test.big")
```

## TODO
- [ ] Investigate and implement proper compression (refpack)
