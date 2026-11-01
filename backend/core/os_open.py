"""Open files and folders in the OS shell."""

import os
import subprocess
import sys
from pathlib import Path


def open_path(path: Path) -> None:
    """Open a file in its default application, or a folder in the file explorer.

    Args:
        path: File or folder to open.
    """
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def reveal_path(path: Path) -> None:
    """Show a file selected in its folder in the file explorer.

    Args:
        path: File to reveal.
    """
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        # xdg-open has no select flag, so open the containing folder instead.
        subprocess.Popen(["xdg-open", str(path.parent)])
