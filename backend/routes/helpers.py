"""Shared state and helper functions used across route modules.

Centralises module-level singletons (game adapter, cancel-event dicts,
env-file path) and pure-logic helpers that multiple routers depend on.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.models import LocString

from fastapi import HTTPException

from backend import config
from backend.translation.game_storage import GameStorage
from backend.translation.orchestrator import fill_duplicate_translations
from backend.games.registry import get_adapter
from backend.games.base import GameAdapter
from backend.data.mod_settings import load_source_language_override, load_target_language_override
from backend.data.progress_tracker import ProgressTracker
from backend.data.translation_store import load_translations
from backend.core.json_store import write_json, write_text_atomic

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_adapter: GameAdapter = get_adapter(config.ACTIVE_GAME)
"""Cached active game adapter. Use `current_adapter()` to read."""


def current_adapter() -> GameAdapter:
    """Return the currently-active game adapter.

    Always reflects `config.ACTIVE_GAME`; rotates lazily after
    `set_active_game` flips the config value.
    """
    global _adapter
    if _adapter.game_id != config.ACTIVE_GAME:
        _adapter = get_adapter(config.ACTIVE_GAME)
    return _adapter


_chrono_ark_adapter: GameAdapter | None = None
"""Cached Chrono Ark adapter. Use `chrono_ark_adapter()` to read."""


def chrono_ark_adapter() -> GameAdapter:
    """Return the Chrono Ark adapter used by the routes mounted under `/api/games/chrono_ark`.

    Those routes serve Chrono Ark whatever the persisted `active_game` is, since the game comes from the URL.

    Returns:
        The cached Chrono Ark adapter instance.
    """
    global _chrono_ark_adapter
    if _chrono_ark_adapter is None:
        _chrono_ark_adapter = get_adapter("chrono_ark")
    return _chrono_ark_adapter


def set_active_game(game_id: str) -> None:
    """Update active game in config and rotate the cached adapter.

    Args:
        game_id: Adapter id to switch to.

    Raises:
        ValueError: If `game_id` is not a registered adapter.
    """
    global _adapter
    new_adapter = get_adapter(game_id)
    config.ACTIVE_GAME = game_id
    _adapter = new_adapter


_active_translations: dict[str, threading.Event] = {}
"""Active translation cancel events, keyed by mod_id."""

_gguf_download_cancels: dict[str, asyncio.Event] = {}
"""Active GGUF download cancel events, keyed by filename."""

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
"""Path to the backend `.env` configuration file."""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def resolve_source_language(
    loc_str: LocString,
    override: str | None,
) -> str | None:
    """Determine source language for a string, respecting a per-mod override.

    If an override is set and the string has content in that language column,
    the override is used. Otherwise falls back to auto-detection.

    Args:
        loc_str: The localization string to check.
        override: Per-mod language override, or None for auto-detect.

    Returns:
        The source language name, or None if no source text is found.
    """
    if override:
        if override in loc_str.translations and loc_str.translations[override]:
            return override
        return None
    return chrono_ark_adapter().detect_source_language(loc_str)


def _stamp_raw_responses(responses: list[dict]) -> list[dict]:
    """Add an ISO-8601 UTC timestamp to each raw API response dict.

    Args:
        responses: List of response dicts from the translation provider.

    Returns:
        The same list, modified in-place with a `timestamp` key added to
        each dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    for r in responses:
        r["timestamp"] = now
    return responses


def _fill_duplicate_translations(
    translations: dict[str, str],
    entries: list[tuple[str, str]],
) -> dict[str, str]:
    """Fill missing keys whose source text matches an already-translated entry.

    LLMs often deduplicate identical source strings and only return one key in
    the response.  This copies the translation to every other key that shares
    the same source text so nothing is left as "Pending translation...".

    Args:
        translations: Mutable dict of key -> English text returned by the LLM.
            Modified in-place to include any missing duplicate keys.
        entries: Original (key, source_text) tuples sent to the provider.
    """
    return fill_duplicate_translations(translations, entries)


def _filter_suggestions(
    suggestions: list[dict],
    strings: dict,
) -> list[dict]:
    """Filter suggestions to only those whose terms appear in actual text.

    Removes suggestions where the source/english term only appears in
    localization keys but not in the actual source text or English translations.

    Args:
        suggestions: Raw suggestion dicts from the provider.
        strings: The full strings dict mapping key -> LocalizedString.

    Returns:
        Filtered list of suggestion dicts.
    """
    all_source_texts: set[str] = set()
    all_english_texts: set[str] = set()
    for _key, loc_str in strings.items():
        for lang_name, text in loc_str.translations.items():
            if lang_name == "English":
                all_english_texts.add(text.lower())
            else:
                all_source_texts.add(text.lower())
    filtered = []
    for suggestion in suggestions:
        source_term = suggestion.get("source", "").lower()
        english_term = suggestion.get("english", "").lower()
        if not source_term and not english_term:
            continue
        source_found = any(source_term in text for text in all_source_texts) if source_term else False
        english_found = any(english_term in text for text in all_english_texts) if english_term else False
        if source_found or english_found:
            filtered.append(suggestion)
    return filtered


def _find_mod(mod_id: str):
    """Find a mod by ID, returning the full ModInfo object.

    Args:
        mod_id: The workshop identifier of the mod.

    Returns:
        The `ModInfo` object for the matching mod.

    Raises:
        HTTPException: 404 if no mod with the given id is found.
    """
    mods = chrono_ark_adapter().scan_mods()
    matching = [m for m in mods if m.mod_id == mod_id]
    if not matching:
        raise HTTPException(status_code=404, detail="Mod not found")
    return matching[0]


def _find_mod_path(mod_id: str) -> Path:
    """Find the mod directory path by scanning all workshop mods.

    Args:
        mod_id: The workshop identifier of the mod.

    Returns:
        The filesystem `Path` to the mod's root directory.

    Raises:
        HTTPException: 404 if no mod with the given id is found.
    """
    mods = chrono_ark_adapter().scan_mods()
    matching = [m for m in mods if m.mod_id == mod_id]
    if not matching:
        raise HTTPException(status_code=404, detail="Mod not found")
    return matching[0].path


def _merge_gdata_originals(
    mod_id: str,
    strings: dict[str, "LocString"],
    target_lang: str = "English",
) -> None:
    """Restore original source text for gdata entries from backup.

    After exporting translations into gdata JSON files, re-extraction
    picks up the target language text but loses the original source language.
    This helper reads the backed-up originals and merges any missing
    source-language translations back into the live entries.

    Args:
        mod_id: The mod's Workshop ID.
        strings: Live localization strings to merge into.
        target_lang: The translation target language (excluded from merge).
    """
    from backend.games.chrono_ark import gdata_extractor

    backup_dir = GameStorage("chrono_ark").mod_dir(mod_id) / "original_gdata"
    if not backup_dir.exists():
        return

    # Extract strings from the backed-up originals.
    originals: dict[str, "LocString"] = {}
    for json_file in sorted(backup_dir.glob("*.json")):
        originals.update(gdata_extractor._extract_gdata_file(json_file))

    # Merge: restore any source-language translations missing from live.
    for key, orig in originals.items():
        if key not in strings:
            continue
        live = strings[key]
        for lang, text in orig.translations.items():
            if lang != target_lang and lang not in live.translations:
                live.translations[lang] = text


def _find_mod_preview_image(mod_path: Path) -> Optional[Path]:
    """Find a preview image in the mod's root directory.

    Searches for `.png`, `.jpg`, and `.jpeg` files and returns the
    first match found.

    Args:
        mod_path: Filesystem path to the mod's root directory.

    Returns:
        The `Path` to the first image found, or `None` if the mod has
        no preview image.
    """
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        for img in mod_path.glob(ext):
            return img
    return None


def _compute_export_snapshot(mod_id: str, mod_path: Path, mod_name: str = "") -> str:
    """Compute a SHA-256 hash of the current translations, mod CSVs, and overrides.

    Combines the `translations.json` content with the mod's CSV file contents
    and the mod's entries in the Harmony injector override JSONs so we can
    detect changes on any side (new translations, mod author updates, or
    external edits to the override files). Excludes timestamps so
    metadata-only changes don't trigger a false "needs export" signal.

    Args:
        mod_id: The mod's Workshop ID.
        mod_path: Filesystem path to the mod's root directory.
        mod_name: Display name used as the key in override JSONs. When empty,
            looked up via `_find_mod` only if the overrides directory exists.

    Returns:
        Hex-digest hash string representing the current state.
    """
    h = hashlib.sha256()

    # Hash translation text content only (excludes timestamps so metadata
    # changes don't trigger a false "needs export" signal).
    flat = load_translations(mod_id)
    if flat:
        h.update(json.dumps(flat, sort_keys=True).encode("utf-8"))

    # Hash each mod CSV file.
    for csv_path in sorted(_get_mod_csv_paths(mod_path)):
        h.update(csv_path.name.encode("utf-8"))
        h.update(csv_path.read_bytes())

    # Hash this mod's entries in the Harmony injector override JSONs.
    # Include a sentinel when the overrides directory exists so the hash
    # changes when the injector is installed or uninstalled.
    overrides_dir = chrono_ark_adapter().get_translation_overrides_dir()
    if overrides_dir:
        h.update(b"overrides_dir_present")
        if not mod_name:
            mod_name = _find_mod(mod_id).name
        for json_name in ("keyed_overrides.json", "text_overrides.json"):
            json_path = overrides_dir / json_name
            if not json_path.exists():
                continue
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            mod_entries = data.get(mod_name)
            if mod_entries:
                h.update(json_name.encode("utf-8"))
                h.update(json.dumps(mod_entries, sort_keys=True).encode("utf-8"))

    return h.hexdigest()


def _compute_csv_snapshot(mod_path: Path) -> str:
    """Compute a SHA-256 hash of only the mod's CSV files.

    Unlike `_compute_export_snapshot`, this excludes translations so it
    can detect mod-author CSV updates without being affected by new
    user translations.

    Args:
        mod_path: Filesystem path to the mod's root directory.

    Returns:
        Hex-digest hash string representing the current CSV state.
    """
    h = hashlib.sha256()
    for csv_path in sorted(_get_mod_csv_paths(mod_path)):
        h.update(csv_path.name.encode("utf-8"))
        h.update(csv_path.read_bytes())
    return h.hexdigest()


def _load_last_export_hash(mod_id: str) -> str:
    """Load the snapshot hash saved after the last successful export.

    Args:
        mod_id: The workshop identifier of the mod.

    Returns:
        The hex-digest hash string, or an empty string if no export has
        been recorded yet.
    """
    path = GameStorage("chrono_ark").mod_file(mod_id, "last_export.json")
    if not path.exists():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("hash", "")
    except Exception:
        return ""


def _save_last_export_hash(mod_id: str, snapshot_hash: str) -> None:
    """Save the snapshot hash after a successful export.

    Args:
        mod_id: The workshop identifier of the mod.
        snapshot_hash: The hex-digest hash string to persist.
    """
    path = GameStorage("chrono_ark").mod_file(mod_id, "last_export.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"hash": snapshot_hash}, indent=None)


def _get_mod_csv_paths(mod_path: Path) -> list[Path]:
    """Collect all CSV file paths for a mod.

    Gathers CSVs from the `Localization/` subdirectory and any top-level
    `Lang*.csv` files in the mod root.

    Args:
        mod_path: Filesystem path to the mod's root directory.

    Returns:
        A list of `Path` objects pointing to each discovered CSV file.
    """
    paths = []
    loc_dir = mod_path / "Localization"
    if loc_dir.exists():
        paths.extend(loc_dir.glob("*.csv"))
    paths.extend(mod_path.glob("Lang*.csv"))
    return paths


def _recalculate_mod_progress(mod_id: str, mod_path: Path) -> None:
    """Re-extract strings and recalculate translation progress for a mod.

    Mirrors the progress-update logic in `get_mod_detail`: extracts all
    localization strings from the mod's files on disk, layers any saved
    user translations on top, then updates the `ProgressTracker` snapshot
    so that `get_status` returns accurate totals/translated counts.

    A string is considered translated when it has a non-empty English value
    **or** its source text is blank (nothing to translate).

    Args:
        mod_id: Workshop identifier of the mod (e.g. "12345").
        mod_path: Filesystem path to the mod's workshop directory.
    """
    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(mod_id) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)

    # Apply saved translations.
    translations = load_translations(mod_id)
    for key, translated_text in translations.items():
        if key in strings:
            strings[key].translations[target_lang] = translated_text

    # When the Harmony injection mod is installed, DLL strings become
    # translatable — clear their untranslatable_reason so the progress
    # tracker includes them in total_keys.
    has_harmony_mod = chrono_ark_adapter().get_translation_overrides_dir() is not None
    if has_harmony_mod:
        for key, loc_str in strings.items():
            if key.startswith("DLL/") and loc_str.untranslatable_reason:
                loc_str.untranslatable_reason = ""

    # Update the progress snapshot.
    tracker = ProgressTracker()
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)

    # Compute translated keys the same way get_mod_detail does.
    lang_override = load_source_language_override(mod_id)
    translated_keys = []
    for key, loc_str in strings.items():
        source_lang = resolve_source_language(loc_str, lang_override)
        source_text = loc_str.translations.get(source_lang, "") if source_lang else ""
        target_text = loc_str.translations.get(target_lang, "")
        if not source_text and target_text:
            source_text = target_text
        if source_text.strip() and bool(target_text):
            translated_keys.append(key)

    tracker.set_translated(mod_id, translated_keys)


def _format_env_value(value: str) -> str:
    """Quote a .env value only when python-dotenv would otherwise misread it.

    Args:
        value: The raw setting value.

    Returns:
        The value as it should appear after `KEY=`.
    """
    # Plain values stay unquoted because vite.config.ts reads SWMT_API_PORT with a bare regex.
    if value == value.strip() and not any(c in value for c in "#$\n\r") and not value.startswith(("'", '"')):
        return value
    # Single quotes turn off ${VAR} expansion, and dotenv only unescapes \\ and \' inside them.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _update_env_file(updates: dict[str, str]) -> None:
    """Write updated SWMT_* values to the .env file and os.environ.

    Reads the existing .env line-by-line, replacing matching keys in place
    to preserve comments and ordering. Keys not already present are appended
    at the end. Also updates `os.environ` so the running process sees the
    new values immediately.

    Args:
        updates: Mapping of env-var names (e.g. `SWMT_BATCH_SIZE`) to their
            new string values.
    """
    lines: list[str] = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)

    # Replace existing keys in place; track which ones we found.
    found_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0]
            if key in updates:
                new_lines.append(f"{key}={_format_env_value(updates[key])}\n")
                found_keys.add(key)
                continue
        new_lines.append(line if line.endswith("\n") else line + "\n")

    # Append any keys that weren't already in the file.
    for key, value in updates.items():
        if key not in found_keys:
            new_lines.append(f"{key}={_format_env_value(value)}\n")

    write_text_atomic(_ENV_PATH, "".join(new_lines))

    # Mirror into os.environ so config reads are consistent within the
    # current process without needing a restart.
    for key, value in updates.items():
        os.environ[key] = value


def _mask_key(key: str) -> str:
    """Return a masked version of an API key for safe display.

    Args:
        key: The raw API key string.

    Returns:
        A string like `"••••ab12"` showing only the last 4 characters,
        or an empty string if the key is not set.
    """
    if not key or not key.strip():
        return ""
    return "••••" + key[-4:]
