"""Load, save and build WH3 parent source snapshots.

A snapshot maps `filename -> key -> {hash, text}` for the parent text the user last translated against.
Drifted entries are kept so the row stays `changed`.
"""

from __future__ import annotations

import json

from backend.core.json_store import write_json
from backend.core.paths import mods_path
from backend.games.total_war_warhammer_3 import GAME_ID
from backend.games.total_war_warhammer_3.loc_extractor import LocRow
from backend.games.total_war_warhammer_3.translation_drift import entry_hash, hash_text, make_entry


def _copy(snapshot: dict) -> dict:
    return {fn: dict(entries) for fn, entries in snapshot.items()}


def refresh_unchanged(snapshot: dict, parent: dict[str, dict[str, LocRow]]) -> dict:
    """Return a copy of `snapshot` with current entries for every parent key whose source did not drift.

    New keys get an entry. A matching hash is rewritten as `{hash, text}`, which backfills legacy text. A differing hash keeps the old entry.
    Keys missing from `parent` are kept.

    Args:
        snapshot: Current snapshot, `{filename: {key: entry}}`.
        parent: Current parent strings, `{filename: {key: LocRow}}`.

    Returns:
        New snapshot dict, input unmodified.
    """
    out = _copy(snapshot)
    for filename, rows in parent.items():
        entries = out.setdefault(filename, {})
        for key, row in rows.items():
            recorded = entry_hash(entries.get(key))
            if recorded is None or recorded == hash_text(row.text):
                entries[key] = make_entry(row.text)
    return out


def accept_keys(snapshot: dict, parent: dict[str, dict[str, LocRow]], keys: set[str]) -> dict:
    """Return a copy of `snapshot` where each key in `keys` takes the current parent text as its baseline.

    Args:
        snapshot: Current snapshot, `{filename: {key: entry}}`.
        parent: Current parent strings, `{filename: {key: LocRow}}`.
        keys: Loc keys to re-baseline.

    Returns:
        New snapshot dict, input unmodified.
    """
    out = _copy(snapshot)
    for filename, rows in parent.items():
        for key, row in rows.items():
            if key in keys:
                out.setdefault(filename, {})[key] = make_entry(row.text)
    return out


def load_parent_snapshot(mod_id: str) -> dict[str, dict[str, dict]]:
    """Load the `{filename: {key: {hash, text}}}` snapshot, defaulting to empty.

    Legacy files stored a bare hash string per key, which loads as `{"hash": <string>, "text": None}`.

    Args:
        mod_id: Mod id.

    Returns:
        Filename to key/entry pairs, or empty dict.
    """
    path = mods_path(GAME_ID) / mod_id / "parent_snapshot.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return {fn: {k: (v if isinstance(v, dict) else {"hash": v, "text": None}) for k, v in entries.items()} for fn, entries in raw.items()}


def save_parent_snapshot(mod_id: str, snapshot: dict[str, dict[str, dict]]) -> None:
    """Persist the parent-text-hash snapshot for the WH3 mod.

    Args:
        mod_id: Mod id.
        snapshot: Filename to key to `{hash, text}` entry.
    """
    path = mods_path(GAME_ID) / mod_id / "parent_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, snapshot)
