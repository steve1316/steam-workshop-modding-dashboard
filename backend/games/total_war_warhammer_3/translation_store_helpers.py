"""Thin wrappers binding the shared per-mod storage helpers to the WH3 game id.

`backend/data/translation_store.py` and `backend/data/character_context.py` default to the Chrono Ark storage root, so these inject the WH3 root.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.json_store import write_json
from backend.data import character_context as cc
from backend.data import translation_store as ts
from backend.games.storage_paths import game_storage_path

GAME_ID = "total_war_warhammer_3"


def _root() -> Path:
    return game_storage_path(GAME_ID)


def load_translations(mod_id: str) -> dict[str, str]:
    """Load `{key: text}` for the WH3 mod.

    Args:
        mod_id: Mod id.

    Returns:
        Translation key to text.
    """
    return ts.load_translations(mod_id, storage_path=_root())


def load_translations_raw(mod_id: str) -> dict[str, dict]:
    """Load `{key: {text, created_at, updated_at}}` for the WH3 mod.

    Args:
        mod_id: Mod id.

    Returns:
        Translation key to timestamped entry.
    """
    return ts.load_translations_raw(mod_id, storage_path=_root())


def save_translations_raw(mod_id: str, data: dict[str, dict]) -> None:
    """Persist the full timestamped dict for the WH3 mod.

    Args:
        mod_id: Mod id.
        data: Translation key to timestamped entry.
    """
    path = _root() / "mods" / mod_id / "translations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)


def load_character_context(mod_id: str) -> dict:
    """Load mod-context for the WH3 mod (repurposed character_context schema).

    Args:
        mod_id: Mod id.

    Returns:
        Mod context fields (source_game, character_name, etc).
    """
    return cc.load_character_context(mod_id, storage_path=_root())


def save_character_context(mod_id: str, ctx: dict) -> None:
    """Save mod-context for the WH3 mod.

    Args:
        mod_id: Mod id.
        ctx: Mod context fields to persist.
    """
    cc.save_character_context(mod_id, ctx, storage_path=_root())


def load_include_translated_names(mod_id: str) -> bool:
    """Load whether translated names outside the glossary are sent with every prompt.

    Args:
        mod_id: Mod id.

    Returns:
        Saved setting, or False when never saved or unreadable.
    """
    path = _root() / "mods" / mod_id / "prompt_options.json"
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            return bool(json.load(f).get("include_translated_names", False))
    except (json.JSONDecodeError, OSError, AttributeError):
        return False


def save_include_translated_names(mod_id: str, value: bool) -> None:
    """Save whether translated names outside the glossary are sent with every prompt.

    Args:
        mod_id: Mod id.
        value: Setting to save.
    """
    path = _root() / "mods" / mod_id / "prompt_options.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"include_translated_names": value})


def load_parent_snapshot(mod_id: str) -> dict[str, dict[str, dict]]:
    """Load the `{filename: {key: {hash, text}}}` snapshot, defaulting to empty.

    Legacy files stored a bare hash string per key, which loads as `{"hash": <string>, "text": None}`.

    Args:
        mod_id: Mod id.

    Returns:
        Filename to key/entry pairs, or empty dict.
    """
    path = _root() / "mods" / mod_id / "parent_snapshot.json"
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
    path = _root() / "mods" / mod_id / "parent_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, snapshot)


def parent_pack_cache_dir(parent_workshop_id: str) -> Path:
    """Return the per-parent RPFM extract cache dir.

    Args:
        parent_workshop_id: Workshop id of the parent pack.

    Returns:
        Cache directory.
    """
    return _root() / "parent_pack_cache" / parent_workshop_id
