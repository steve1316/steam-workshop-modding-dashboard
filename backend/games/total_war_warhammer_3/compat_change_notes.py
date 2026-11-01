"""Bridge to totalwar-modding's Workshop change notes for WH3 compat packs.

Runs `python -m publish.change_notes` inside helper_scripts (its publish state paths are relative to it) so `update.py` and the app agree.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from backend import config
from backend.games.total_war_warhammer_3.routes._paths import helper_scripts_path

# `preview` hashes each pack and can be slow. Publish All sends every pack in one call, so the timeout scales with the id count.
PREVIEW_TIMEOUT_SECONDS = 60
PER_PACK_SECONDS = 15
RECORD_TIMEOUT_SECONDS = 30


class ChangeNoteError(Exception):
    """Raised when the change note CLI cannot run or returns something unusable."""


def _run_cli(args: list[str], timeout: int) -> str:
    """Run the change note CLI from the helper_scripts directory.

    Args:
        args: Arguments after `python -m publish.change_notes`.
        timeout: Seconds before giving up.

    Returns:
        Captured stdout.
    """
    helper = helper_scripts_path()
    if not config.TW3_HELPER_PATH or not helper.is_dir():
        raise ChangeNoteError("helper_scripts path is not configured")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "publish.change_notes", *args],
            cwd=str(helper),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "STEAM_LIBRARY_DRIVE": config.TW3_STEAM_LIBRARY_DRIVE or ""},
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        raise ChangeNoteError(f"change note script timed out after {timeout}s") from None
    except OSError as exc:
        raise ChangeNoteError(f"could not run the change note script: {exc}") from exc
    if proc.returncode != 0:
        lines = [line for line in (proc.stderr or "").splitlines() if line.strip()]
        raise ChangeNoteError(lines[-1] if lines else f"change note script exited with code {proc.returncode}")
    return proc.stdout or ""


def preview(ids: list[str]) -> dict[str, dict | None]:
    """Fetch the note each compat pack would be uploaded with right now.

    Args:
        ids: Workshop ids of the compat packs.

    Returns:
        Id to `{"note", "pack_sha", "pending"}`, or None when not a generated pack or its file is missing.
    """
    if not ids:
        return {}
    timeout = PREVIEW_TIMEOUT_SECONDS + PER_PACK_SECONDS * len(ids)
    stdout = _run_cli(["preview", *ids], timeout)
    # Helper imports may print before the JSON, so parse only the last non-empty line.
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        data = json.loads(lines[-1]) if lines else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ChangeNoteError("change note script did not print a JSON object")
    return {wid: data.get(wid) for wid in ids}


def record(workshop_id: str, pack_sha: str, note: str) -> None:
    """Record a successful compat pack upload in totalwar-modding's publish state.

    The note goes through a UTF-8 temp file so multi-line text with quotes and non-ASCII characters survives.

    Args:
        workshop_id: Workshop id of the uploaded pack.
        pack_sha: Pack SHA-256 captured when the upload started.
        note: Changenote sent with the upload.
    """
    fd, path = tempfile.mkstemp(prefix=f"changenote_{workshop_id}_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(note)
        _run_cli(["record", workshop_id, "--pack-sha", pack_sha, "--note-file", path], RECORD_TIMEOUT_SECONDS)
    finally:
        Path(path).unlink(missing_ok=True)
