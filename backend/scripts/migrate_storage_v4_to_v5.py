"""One-time migration: convert WH3 `snapshots/<id>.json` files into the shared `history/` backup folders.

Idempotent via a marker file.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from backend.core.json_store import write_json, write_text_atomic
from backend.core.settings import settings
from backend.data.history_manager import new_backup_dir

LOG = logging.getLogger(__name__)

_GAME_ID = "total_war_warhammer_3"
_MARKER_RELATIVE = Path("_migrations") / "v4_to_v5_complete.marker"

# Snapshot JSON key to the mod-dir file it captured.
_CAPTURED = {
    "translations_raw": "translations.json",
    "parent_snapshot": "parent_snapshot.json",
    "api_responses": "api_responses.json",
    "glossary": "glossary.json",
}


def _root() -> Path:
    """Return the configured storage root."""
    return Path(settings.storage_path)


def _marker_path() -> Path:
    """Return the migration completion marker path."""
    return _root() / _MARKER_RELATIVE


def _read_json(path: Path, default):
    """Read JSON, or `default` when missing or unreadable."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _timestamp(created_at: str) -> str:
    """Turn an ISO creation time into a backup folder timestamp, falling back to the epoch for a bad value."""
    try:
        return datetime.fromisoformat(created_at).strftime("%Y%m%d_%H%M%S")
    except (TypeError, ValueError):
        return "19700101_000000"


def _convert_snapshot(snapshot: dict, hist_dir: Path) -> None:
    """Write one old snapshot as a history backup folder.

    Args:
        snapshot: The parsed `snapshots/<id>.json` body.
        hist_dir: The mod's `history/` directory.
    """
    created_at = snapshot.get("created_at", "")
    backup_dir = new_backup_dir(hist_dir, _timestamp(created_at))
    files = []
    for key, filename in _CAPTURED.items():
        if key in snapshot:
            write_json(backup_dir / filename, snapshot[key])
            files.append(filename)

    external: dict[str, str] = {}
    for i, (original, body) in enumerate(snapshot.get("loc_tsv_files", {}).items()):
        stored = f"external/{i}_{Path(original).name}"
        write_text_atomic(backup_dir / stored, body)
        external[stored] = original

    meta = {
        "timestamp": backup_dir.name,
        "reason": snapshot.get("label", ""),
        "kind": snapshot.get("kind", "auto"),
        "created_at": created_at,
        "files": files,
        "external": external,
        "translated_count": 0,
        "total_count": 0,
        "glossary_count": len(snapshot.get("glossary", {}).get("terms", {})),
    }
    write_json(backup_dir / "meta.json", meta)


def run_migration() -> bool:
    """Convert every WH3 mod's old snapshots into history backups if not already done.

    Returns:
        Whether the migration ran.
    """
    marker = _marker_path()
    if marker.exists():
        LOG.info("Storage migration v4->v5 already complete; skipping.")
        return False

    mods_dir = _root() / "games" / _GAME_ID / "mods"
    if mods_dir.is_dir():
        for mod_dir in mods_dir.iterdir():
            snaps_dir = mod_dir / "snapshots"
            if not snaps_dir.is_dir():
                continue
            # The index is oldest first, so same-second snapshots keep their order through the folder suffixes.
            for entry in _read_json(snaps_dir / "index.json", []):
                snapshot = _read_json(snaps_dir / f"{entry.get('ulid', '')}.json", None)
                if isinstance(snapshot, dict):
                    _convert_snapshot(snapshot, mod_dir / "history")
            shutil.rmtree(snaps_dir)

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("v4->v5 migration complete\n", encoding="utf-8")
    LOG.info("Storage migration v4->v5 complete; marker written at %s", marker)
    return True
