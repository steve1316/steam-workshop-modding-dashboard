"""Centralized read/write operations for per-mod translations.json files.

Encapsulates the storage format change from flat ``{"key": "text"}`` to
``{"key": {"text": "...", "created_at": "...", "updated_at": "..."}}``.
All consumers that only need the translated text should use `load_translations`
which returns the legacy flat dict regardless of on-disk format.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.games.storage_paths import mods_path
from backend.core.json_store import write_json


def _translations_path(mod_id: str, storage_path: Optional[Path] = None) -> Path:
    """Build the path to a mod's `translations.json` file.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        Path to the mod's translations JSON file.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    return mods_dir / mod_id / "translations.json"


def _normalize_entry(value: str | dict) -> dict:
    """Normalize a translation entry to the timestamped dict format.

    Args:
        value: Either a plain string (old format) or a dict with `text`,
            `created_at`, and `updated_at` keys (new format).

    Returns:
        A dict with `text`, `created_at`, and `updated_at` keys.
    """
    if isinstance(value, str):
        return {"text": value, "created_at": None, "updated_at": None}
    return value


def _load_raw_data(path: Path) -> dict:
    """Load raw JSON from disk, returning empty dict if missing or corrupt.

    Args:
        path: Filesystem path to the JSON file.

    Returns:
        Parsed JSON dict, or an empty dict on any read/parse failure.
    """
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw_data(path: Path, data: dict) -> None:
    """Write the full timestamped dict to disk.

    Creates parent directories if they don't exist.

    Args:
        path: Filesystem path to write the JSON file.
        data: The translations dict to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)


def load_translations(mod_id: str, *, storage_path: Optional[Path] = None) -> dict[str, str]:
    """Load translations as a flat ``{key: text}`` dict.

    Handles both the old flat format and the new timestamped format
    transparently. This is the primary read function for all consumers
    that only need the translated text.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        Dictionary mapping localization keys to English translation strings.
    """
    raw = _load_raw_data(_translations_path(mod_id, storage_path))
    result: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            result[key] = value
        elif isinstance(value, dict):
            result[key] = value.get("text", "")
        else:
            result[key] = ""
    return result


def load_translations_raw(mod_id: str, *, storage_path: Optional[Path] = None) -> dict[str, dict]:
    """Load translations in full timestamped format.

    Old flat string entries are normalized to
    ``{"text": "...", "created_at": None, "updated_at": None}``.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        Dictionary mapping localization keys to timestamped entry dicts.
    """
    raw = _load_raw_data(_translations_path(mod_id, storage_path))
    return {key: _normalize_entry(value) for key, value in raw.items()}


def save_translations_bulk(
    mod_id: str,
    new_entries: dict[str, str],
    *,
    storage_path: Optional[Path] = None,
) -> None:
    """Merge new flat translations into the existing timestamped store.

    For genuinely new keys, both `created_at` and `updated_at` are set.
    For existing keys whose text changed, only `updated_at` is refreshed.
    Existing keys whose text is unchanged are left untouched.

    Args:
        mod_id: The mod's Workshop ID.
        new_entries: Flat ``{key: english_text}`` dict of translations to merge.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    path = _translations_path(mod_id, storage_path)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(timezone.utc).isoformat()

    for key, text in new_entries.items():
        if key in existing:
            if existing[key]["text"] != text:
                existing[key]["text"] = text
                existing[key]["updated_at"] = now
        else:
            existing[key] = {"text": text, "created_at": now, "updated_at": now}

    _save_raw_data(path, existing)


def update_single_translation(
    mod_id: str,
    key: str,
    text: str,
    *,
    storage_path: Optional[Path] = None,
) -> None:
    """Update a single translation key (for manual edits).

    Sets `created_at` if the key is new, and always updates `updated_at`.

    Args:
        mod_id: The mod's Workshop ID.
        key: The localization key.
        text: The new English translation text.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    path = _translations_path(mod_id, storage_path)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(timezone.utc).isoformat()

    if key in existing:
        existing[key]["text"] = text
        existing[key]["updated_at"] = now
    else:
        existing[key] = {"text": text, "created_at": now, "updated_at": now}

    _save_raw_data(path, existing)


def clear_all_translations(
    mod_id: str,
    keys: list[str],
    *,
    storage_path: Optional[Path] = None,
) -> None:
    """Set the given keys to empty strings, updating `updated_at`.

    Keys that don't already exist are created with empty text.

    Args:
        mod_id: The mod's Workshop ID.
        keys: List of localization keys to clear.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    path = _translations_path(mod_id, storage_path)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(timezone.utc).isoformat()

    for key in keys:
        if key in existing:
            existing[key]["text"] = ""
            existing[key]["updated_at"] = now
        else:
            existing[key] = {"text": "", "created_at": now, "updated_at": now}

    _save_raw_data(path, existing)


def replace_in_translations(
    mod_id: str,
    old_text: str,
    new_text: str,
    *,
    storage_path: Optional[Path] = None,
) -> int:
    """Find-and-replace within translation text values.

    Only updates `updated_at` on entries where a replacement actually occurred.

    Args:
        mod_id: The mod's Workshop ID.
        old_text: The substring to search for.
        new_text: The replacement substring.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        The number of entries that were modified.
    """
    path = _translations_path(mod_id, storage_path)
    existing = {k: _normalize_entry(v) for k, v in _load_raw_data(path).items()}
    now = datetime.now(timezone.utc).isoformat()
    replaced = 0

    for entry in existing.values():
        if old_text in entry["text"]:
            updated = entry["text"].replace(old_text, new_text)
            if updated != entry["text"]:
                entry["text"] = updated
                entry["updated_at"] = now
                replaced += 1

    if replaced:
        _save_raw_data(path, existing)

    return replaced
