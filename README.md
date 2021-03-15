# classify_camera_files
Classifies raw photos and videos from cameras and smartphones to simplify naming and uploading for search.

# How To Use
Execute [classify_camera_files.exe](classify_camera_files.exe) on Windows
or [classify_camera_files](classify_camera_files) on Unix.
Should appear UI (with Russial locale if need).

Note that to choose folder it is necessarily go into it and only next press "OK".

# How To Work with on Unix
- `pip3 install -r requirements.txt`
- for Debian `sudo apt-get install python3-tk`, for Windows Tkinter is packed into Python installer.
- `classify_camera_files.py -h`
- Next see what is better way to use it.

# How To Build Executable file (both Windows and Unix)
- https://www.python.org/downloads/
- Clone/copy repo **on target OS**.
- `pip3 install -r requirements.txt`
- `pyinstaller --clean --onefile -p . classify_camera_files.py` (without '--clean' if first time).
- Resulting executable file will be placed in "dist" folder.
- Try execute from not "dist" folder! Important to ensure that all paths are relative.

### Roadmap
- Simple classification strategy by time + files number
    - ~~MVP~~
    - ~~Localization~~
    - ~~UI to choose folders~~
    - ~~git repo~~
    - ~~UI with progress~~
    - ~~UI with actions~~
    - UI with fine tuning (really need?)
    - Faster parsing (really need?)
    - Explain actions in console
- Parse tags from video
- Classify with ML like https://www.pyimagesearch.com/2017/03/20/imagenet-vggnet-resnet-inception-xception-keras/
