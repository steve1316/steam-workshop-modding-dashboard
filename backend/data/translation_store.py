"""Read/write for per-mod translations.json, stored as `{key: {text, created_at, updated_at, provider}}` (legacy files were flat `{key: text}`).

Consumers that only need the text should use `load_translations`, which returns the flat dict for either format.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path


def _translations_path(mod_id: str, *, game_id: str) -> Path:
    """Build the path to a mod's `translations.json`.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        The translations file path.
    """
    mods_dir = mods_path(game_id)
    return mods_dir / mod_id / "translations.json"


def _normalize_entry(value: str | dict) -> dict:
    """Normalize a translation entry to the timestamped dict format.

    Args:
        value: Plain string (old format) or timestamped dict.

    Returns:
        Dict with `text`, `created_at` and `updated_at`.
    """
    if isinstance(value, str):
        return {"text": value, "created_at": None, "updated_at": None}
    return value


def _load_raw_data(path: Path) -> dict:
    """Load raw JSON from disk, returning an empty dict if missing or corrupt.

    Args:
        path: JSON file.

    Returns:
        Parsed dict, empty on any read/parse failure.
    """
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw_data(path: Path, data: dict) -> None:
    """Write the full timestamped dict to disk.

    Args:
        path: JSON file.
        data: Translations dict.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)


def load_translations(mod_id: str, *, game_id: str) -> dict[str, str]:
    """Load translations as a flat `{key: text}` dict, whichever format is on disk.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Localization key to English text.
    """
    raw = _load_raw_data(_translations_path(mod_id, game_id=game_id))
    result: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            result[key] = value
        elif isinstance(value, dict):
            result[key] = value.get("text", "")
        else:
            result[key] = ""
    return result


def load_translations_raw(mod_id: str, *, game_id: str) -> dict[str, dict]:
    """Load translations in full timestamped format, normalizing old flat entries with `None` timestamps.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Localization key to timestamped entry.
    """
    raw = _load_raw_data(_translations_path(mod_id, game_id=game_id))
    return {key: _normalize_entry(value) for key, value in raw.items()}


def load_providers(mod_id: str, *, game_id: str) -> dict[str, str]:
    """Load which provider wrote each translation.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Localization key to provider id, for keys that record one.
    """
    raw = _load_raw_data(_translations_path(mod_id, game_id=game_id))
    return {key: value["provider"] for key, value in raw.items() if isinstance(value, dict) and value.get("provider")}


def save_translations_raw(mod_id: str, data: dict[str, dict], *, game_id: str) -> None:
    """Replace the full timestamped store for a mod.

    Args:
        mod_id: Mod's Workshop id.
        data: Localization key to timestamped entry.
        game_id: Game the mod belongs to.
    """
    _save_raw_data(_translations_path(mod_id, game_id=game_id), data)


def save_translations_bulk(
    mod_id: str,
    new_entries: dict[str, str],
    *,
    game_id: str,
    provider: str | None = None,
) -> None:
    """Merge new flat translations into the existing timestamped store.

    New keys get both timestamps, changed keys only `updated_at`, and unchanged keys are left alone.

    Args:
        mod_id: Mod's Workshop id.
        new_entries: Flat `{key: english_text}` to merge.
        game_id: Game the mod belongs to.
        provider: Provider recorded on every key in `new_entries`, or `None` to keep each key's existing one.
    """
    path = _translations_path(mod_id, game_id=game_id)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(UTC).isoformat()

    for key, text in new_entries.items():
        if key in existing:
            if existing[key]["text"] != text:
                existing[key]["text"] = text
                existing[key]["updated_at"] = now
        else:
            existing[key] = {"text": text, "created_at": now, "updated_at": now}
        if provider:
            existing[key]["provider"] = provider

    _save_raw_data(path, existing)


def update_single_translation(
    mod_id: str,
    key: str,
    text: str,
    *,
    game_id: str,
    provider: str | None = None,
) -> None:
    """Update a single translation key for manual edits.

    Args:
        mod_id: Mod's Workshop id.
        key: Localization key.
        text: New English text.
        game_id: Game the mod belongs to.
        provider: Provider to record on the key, or `None` to keep its existing one.
    """
    path = _translations_path(mod_id, game_id=game_id)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(UTC).isoformat()

    if key in existing:
        existing[key]["text"] = text
        existing[key]["updated_at"] = now
    else:
        existing[key] = {"text": text, "created_at": now, "updated_at": now}
    if provider:
        existing[key]["provider"] = provider

    _save_raw_data(path, existing)


def clear_all_translations(
    mod_id: str,
    keys: list[str],
    *,
    game_id: str,
) -> None:
    """Set the given keys to empty strings, creating any that don't exist.

    Args:
        mod_id: Mod's Workshop id.
        keys: Localization keys to clear.
        game_id: Game the mod belongs to.
    """
    path = _translations_path(mod_id, game_id=game_id)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(UTC).isoformat()

    for key in keys:
        if key in existing:
            existing[key]["text"] = ""
            existing[key]["updated_at"] = now
        else:
            existing[key] = {"text": "", "created_at": now, "updated_at": now}

    _save_raw_data(path, existing)
