"""Shared state and helper functions used across route modules."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.loc import LocString


from backend.core.errors import NotFoundError
from backend.core.json_store import write_json
from backend.core.paths import GameStorage
from backend.core.settings import settings
from backend.games.base import GameAdapter
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.registry import get_adapter
from backend.persistence.mod_settings import load_source_language_override, load_target_language_override
from backend.persistence.progress_tracker import ProgressTracker
from backend.persistence.translation_store import load_translations
from backend.translation.orchestrator import fill_duplicate_translations

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Module-level state

_adapter: GameAdapter = get_adapter(settings.active_game)
"""Cached active game adapter. Use `current_adapter()` to read."""


def current_adapter() -> GameAdapter:
    """Return the active game adapter, rotating lazily after `set_active_game` flips `settings.active_game`."""
    global _adapter
    if _adapter.game_id != settings.active_game:
        _adapter = get_adapter(settings.active_game)
    return _adapter


_chrono_ark_adapter: ChronoArkAdapter | None = None
"""Cached Chrono Ark adapter. Use `chrono_ark_adapter()` to read."""


def chrono_ark_adapter() -> ChronoArkAdapter:
    """Return the Chrono Ark adapter for the `/api/games/chrono_ark` routes, whatever the persisted `active_game` is.

    Returns:
        Cached adapter.
    """
    global _chrono_ark_adapter
    if _chrono_ark_adapter is None:
        _chrono_ark_adapter = ChronoArkAdapter()
    return _chrono_ark_adapter


def set_active_game(game_id: str) -> None:
    """Update active game in config and rotate the cached adapter.

    Args:
        game_id: Adapter id to switch to.
    """
    global _adapter
    new_adapter = get_adapter(game_id)
    settings.active_game = game_id
    _adapter = new_adapter


_active_translations: dict[str, threading.Event] = {}
"""Active translation cancel events, keyed by mod_id."""

_gguf_download_cancels: dict[str, asyncio.Event] = {}
"""Active GGUF download cancel events, keyed by filename."""

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Helper functions


def resolve_source_language(
    loc_str: LocString,
    override: str | None,
) -> str | None:
    """Determine source language for a string, using the per-mod override when that column has content.

    Args:
        loc_str: String to check.
        override: Per-mod override, or None for auto-detect.

    Returns:
        Source language name, or None if no source text.
    """
    if override:
        if override in loc_str.translations and loc_str.translations[override]:
            return override
        return None
    return chrono_ark_adapter().detect_source_language(loc_str)


def _fill_duplicate_translations(
    translations: dict[str, str],
    entries: list[tuple[str, str]],
) -> dict[str, str]:
    """Copy translations to missing keys that share source text, since LLMs often return only one key per duplicate.

    Args:
        translations: Key -> English text from the LLM, modified in place.
        entries: Original (key, source_text) tuples sent to the provider.
    """
    return fill_duplicate_translations(translations, entries)


def _filter_suggestions(
    suggestions: list[dict],
    strings: dict,
) -> list[dict]:
    """Drop suggestions whose terms appear only in localization keys, not in actual text.

    Args:
        suggestions: Raw provider suggestions.
        strings: Key -> LocalizedString.

    Returns:
        Filtered suggestions.
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
    """Find a mod by ID, raising `NotFoundError` if missing.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Matching `ModInfo`.
    """
    mod = chrono_ark_adapter().find_mod(mod_id)
    if mod is None:
        raise NotFoundError("Mod not found")
    return mod


def _find_mod_path(mod_id: str) -> Path:
    """Find the mod directory path, raising 404 if missing.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Mod's root directory.
    """
    return _find_mod(mod_id).path


def _merge_gdata_originals(
    mod_id: str,
    strings: dict[str, LocString],
    target_lang: str = "English",
) -> None:
    """Restore original source text for gdata entries from backup.

    Re-extraction after an export picks up the target language text but loses the original source language.

    Args:
        mod_id: Mod's Workshop id.
        strings: Live strings to merge into.
        target_lang: Target language, excluded from the merge.
    """
    from backend.games.chrono_ark import gdata_extractor

    backup_dir = GameStorage(GAME_ID).mod_dir(mod_id) / "original_gdata"
    if not backup_dir.exists():
        return

    originals: dict[str, LocString] = {}
    for json_file in sorted(backup_dir.glob("*.json")):
        originals.update(gdata_extractor._extract_gdata_file(json_file))

    for key, orig in originals.items():
        if key not in strings:
            continue
        live = strings[key]
        for lang, text in orig.translations.items():
            if lang != target_lang and lang not in live.translations:
                live.translations[lang] = text


def _find_mod_preview_image(mod_path: Path) -> Path | None:
    """Find the first `.png`, `.jpg`, or `.jpeg` in the mod's root directory.

    Args:
        mod_path: Mod's root directory.

    Returns:
        Image path, or `None` if none.
    """
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        for img in mod_path.glob(ext):
            return img
    return None


def _compute_export_snapshot(mod_id: str, mod_path: Path, mod_name: str = "") -> str:
    """Compute a SHA-256 hash of the translations, mod CSVs, and the mod's Harmony override entries.

    Covers every side that can change (new translations, mod author updates, external override edits).

    Args:
        mod_id: Mod's Workshop id.
        mod_path: Mod's root directory.
        mod_name: Key in the override JSONs, looked up via `_find_mod` when empty and the overrides directory exists.

    Returns:
        Hex digest.
    """
    h = hashlib.sha256()

    # Text only, so metadata-only changes don't trigger a false "needs export".
    flat = load_translations(mod_id, game_id=GAME_ID)
    if flat:
        h.update(json.dumps(flat, sort_keys=True).encode("utf-8"))

    for csv_path in sorted(_get_mod_csv_paths(mod_path)):
        h.update(csv_path.name.encode("utf-8"))
        h.update(csv_path.read_bytes())

    # The sentinel makes the hash change when the injector is installed or uninstalled.
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
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            mod_entries = data.get(mod_name)
            if mod_entries:
                h.update(json_name.encode("utf-8"))
                h.update(json.dumps(mod_entries, sort_keys=True).encode("utf-8"))

    return h.hexdigest()


def _compute_csv_snapshot(mod_path: Path) -> str:
    """Compute a SHA-256 hash of only the mod's CSV files, so author updates show up without user translations affecting it.

    Args:
        mod_path: Mod's root directory.

    Returns:
        Hex digest.
    """
    h = hashlib.sha256()
    for csv_path in sorted(_get_mod_csv_paths(mod_path)):
        h.update(csv_path.name.encode("utf-8"))
        h.update(csv_path.read_bytes())
    return h.hexdigest()


def _load_last_export_hash(mod_id: str) -> str:
    """Load the snapshot hash saved after the last successful export.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Hex digest, or an empty string if none recorded.
    """
    path = GameStorage(GAME_ID).mod_file(mod_id, "last_export.json")
    if not path.exists():
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("hash", "")
    except Exception:
        return ""


def _save_last_export_hash(mod_id: str, snapshot_hash: str) -> None:
    """Save the snapshot hash after a successful export.

    Args:
        mod_id: Mod's Workshop id.
        snapshot_hash: Hex digest to persist.
    """
    path = GameStorage(GAME_ID).mod_file(mod_id, "last_export.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"hash": snapshot_hash}, indent=None)


def _get_mod_csv_paths(mod_path: Path) -> list[Path]:
    """Collect CSVs from `Localization/` and top-level `Lang*.csv` files.

    Args:
        mod_path: Mod's root directory.

    Returns:
        CSV paths.
    """
    paths = []
    loc_dir = mod_path / "Localization"
    if loc_dir.exists():
        paths.extend(loc_dir.glob("*.csv"))
    paths.extend(mod_path.glob("Lang*.csv"))
    return paths


def _recalculate_mod_progress(mod_id: str, mod_path: Path) -> None:
    """Re-extract strings and update the `ProgressTracker` snapshot, mirroring `get_mod_detail`.

    A string counts as translated when it has a non-empty target value or its source text is blank.

    Args:
        mod_id: Mod's Workshop id.
        mod_path: Mod's workshop directory.
    """
    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)

    translations = load_translations(mod_id, game_id=GAME_ID)
    for key, translated_text in translations.items():
        if key in strings:
            strings[key].translations[target_lang] = translated_text

    # With the Harmony mod installed, DLL strings become translatable, so clear the reason to count them in total_keys.
    has_harmony_mod = chrono_ark_adapter().get_translation_overrides_dir() is not None
    if has_harmony_mod:
        for key, loc_str in strings.items():
            if key.startswith("DLL/") and loc_str.untranslatable_reason:
                loc_str.untranslatable_reason = ""

    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)

    # Must match how get_mod_detail computes translated keys.
    lang_override = load_source_language_override(mod_id, game_id=GAME_ID)
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


def _mask_key(key: str) -> str:
    """Mask an API key for display.

    Args:
        key: Raw API key.

    Returns:
        Last 4 characters behind a bullet prefix, or an empty string if unset.
    """
    if not key or not key.strip():
        return ""
    return "••••" + key[-4:]
