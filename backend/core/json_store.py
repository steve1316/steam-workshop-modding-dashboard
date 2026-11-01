"""Atomic file writes, so a crash or a full disk mid-write never leaves a truncated file."""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

_REPLACE_ATTEMPTS = 10
_REPLACE_DELAY_SECONDS = 0.05


def _replace_with_retry(src: str, dst: Path) -> None:
    """Move `src` over `dst`, retrying briefly while Windows has `dst` open elsewhere.

    Args:
        src: The finished temp file.
        dst: The file to replace.
    """
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            # Windows refuses to replace a file another thread is reading, and that read is usually over in milliseconds.
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_DELAY_SECONDS)


def write_text_atomic(path: Path, text: str, newline: str | None = None) -> None:
    """Write text to `path` through a temp file in the same folder, then swap it in.

    Args:
        path: The file to write.
        text: The full file contents.
        newline: Passed to `open()`. None matches `Path.write_text`, and "" keeps "\\n" as written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, data: Any, indent: int | None = 2) -> None:
    """Atomically write `data` as UTF-8 JSON.

    Args:
        path: The file to write.
        data: Any JSON-serializable value.
        indent: Indent width, or None for compact output.
    """
    # Serialize first so a bad value fails before the temp file exists.
    write_text_atomic(path, json.dumps(data, indent=indent, ensure_ascii=False))
