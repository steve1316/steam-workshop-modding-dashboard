"""Full-state snapshots for WH3 translation mods.

Each snapshot captures translations.json, parent_snapshot.json, api_responses.json, the mod glossary and every `.loc.tsv` under the mod's local source dir.
Stored per mod under `<root>/mods/{id}/snapshots/`, keeping the last 20.
Ids are monotonic-millisecond + random-suffix strings that sort by creation time.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.core.paths import safe_child
from backend.games.storage_paths import game_storage_path
from backend.core.json_store import write_json, write_text_atomic

GAME_ID = "total_war_warhammer_3"
MAX_SNAPSHOTS = 20


def _mod_dir(mod_id: str) -> Path:
    return game_storage_path(GAME_ID) / "mods" / mod_id


def _snapshots_dir(mod_id: str) -> Path:
    return _mod_dir(mod_id) / "snapshots"


def _index_path(mod_id: str) -> Path:
    return _snapshots_dir(mod_id) / "index.json"


def _new_ulid() -> str:
    """Return a time-sortable snapshot id."""
    return f"{int(time.time() * 1000):013d}-{secrets.token_hex(4)}"


def _read_index(mod_id: str) -> list[dict]:
    p = _index_path(mod_id)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_index(mod_id: str, entries: list[dict]) -> None:
    p = _index_path(mod_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json(p, entries)


def _read_file_or_default(p: Path, default):
    if not p.exists():
        return default
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _gather_loc_tsv_files(local_source_dir: Path | None) -> dict[str, str]:
    """Read every `.loc.tsv` under `<local_source_dir>/text/**` as a flat string map."""
    if local_source_dir is None:
        return {}
    text_dir = local_source_dir / "text"
    if not text_dir.exists():
        return {}
    out: dict[str, str] = {}
    for tsv in text_dir.rglob("*.loc.tsv"):
        try:
            out[str(tsv)] = tsv.read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def create_snapshot(mod_id: str, *, label: str, kind: str, local_source_dir: Path | None = None) -> str:
    """Create a full-state snapshot for a WH3 translation mod.

    Args:
        mod_id: Workshop id of the WH3 mod.
        label: Human-readable description (e.g. `"Auto before Translate"`).
        kind: `"auto"` or `"manual"`.
        local_source_dir: Source dir whose `.loc.tsv` files are included, or `None` to skip.

    Returns:
        Snapshot id.
    """
    sid = _new_ulid()
    mod_dir = _mod_dir(mod_id)

    snapshot = {
        "ulid": sid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "kind": kind,
        "translations_raw": _read_file_or_default(mod_dir / "translations.json", {}),
        "parent_snapshot": _read_file_or_default(mod_dir / "parent_snapshot.json", {}),
        "api_responses": _read_file_or_default(mod_dir / "api_responses.json", []),
        "glossary": _read_file_or_default(mod_dir / "glossary.json", {"terms": {}}),
        "loc_tsv_files": _gather_loc_tsv_files(local_source_dir),
    }

    _snapshots_dir(mod_id).mkdir(parents=True, exist_ok=True)
    snap_path = _snapshots_dir(mod_id) / f"{sid}.json"
    write_json(snap_path, snapshot)

    index = _read_index(mod_id)
    index.append({"ulid": sid, "created_at": snapshot["created_at"], "label": label, "kind": kind})

    # Prune oldest over the cap.
    while len(index) > MAX_SNAPSHOTS:
        oldest = index.pop(0)
        try:
            (_snapshots_dir(mod_id) / f"{oldest['ulid']}.json").unlink(missing_ok=True)
        except OSError:
            pass

    _write_index(mod_id, index)
    return sid


def list_snapshots(mod_id: str) -> list[dict]:
    """List snapshot metadata for a mod, newest first.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{ulid, created_at, label, kind}` entries, empty when none exist.
    """
    return list(reversed(_read_index(mod_id)))


def delete_snapshot(mod_id: str, sid: str) -> None:
    """Delete one snapshot and remove it from the index.

    Args:
        mod_id: Workshop id of the WH3 mod.
        sid: Snapshot id to delete.
    """
    index = _read_index(mod_id)
    index = [e for e in index if e["ulid"] != sid]
    _write_index(mod_id, index)
    try:
        safe_child(_snapshots_dir(mod_id), f"{sid}.json").unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def restore_snapshot(mod_id: str, sid: str, *, local_source_dir: Path | None = None) -> None:
    """Restore a mod's state from a snapshot after taking an auto pre-restore snapshot.

    Writes every captured file back verbatim.
    Snapshots from before glossaries were captured have no `glossary` key, so the current glossary is left alone.

    Args:
        mod_id: Workshop id of the WH3 mod.
        sid: Snapshot id to restore.
        local_source_dir: Source dir re-gathered into the pre-restore snapshot.
    """
    try:
        snap_path = safe_child(_snapshots_dir(mod_id), f"{sid}.json")
    except ValueError:
        snap_path = None
    if snap_path is None or not snap_path.exists():
        raise FileNotFoundError(f"snapshot {sid} not found for mod {mod_id}")

    create_snapshot(mod_id, label=f"pre-restore of {sid}", kind="auto", local_source_dir=local_source_dir)

    with snap_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    mod_dir = _mod_dir(mod_id)
    mod_dir.mkdir(parents=True, exist_ok=True)
    write_json((mod_dir / "translations.json"), snapshot.get("translations_raw", {}))
    write_json((mod_dir / "parent_snapshot.json"), snapshot.get("parent_snapshot", {}))
    write_json((mod_dir / "api_responses.json"), snapshot.get("api_responses", []))
    if "glossary" in snapshot:
        write_json((mod_dir / "glossary.json"), snapshot["glossary"])

    for path_str, body in snapshot.get("loc_tsv_files", {}).items():
        write_text_atomic(Path(path_str), body)
