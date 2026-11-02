"""Chrono Ark mod services shared by the routes and the CLI: extracting, the detail view, exporting into the mod and resetting it."""

import json
import shutil
from pathlib import Path
from typing import Any

from backend.core.errors import DomainError
from backend.core.json_store import write_json
from backend.core.paths import GameStorage
from backend.data.history_manager import create_backup
from backend.data.mod_settings import load_source_language_override, load_target_language_override
from backend.data.progress_tracker import ProgressDiff, ProgressTracker
from backend.data.translation_store import load_providers, load_translations
from backend.games.chrono_ark import GAME_ID
from backend.models import LocString
from backend.routes.helpers import (
    _compute_csv_snapshot,
    _compute_export_snapshot,
    _find_mod,
    _find_mod_path,
    _find_mod_preview_image,
    _get_mod_csv_paths,
    _load_last_export_hash,
    _merge_gdata_originals,
    _save_last_export_hash,
    chrono_ark_adapter,
    resolve_source_language,
)

# Per-mod translation state that Reset deletes. Character context and the mod glossary are user-configured, so they survive.
_RESET_FILES = ("translations.json", "progress.json", "synced_keys.json", "last_export.json", "last_csv_hash.json", "pre_export_english.json", "api_responses.json")
_RESET_DIRS = ("original_csvs", "original_gdata")


def save_extracted_strings(strings: dict[str, LocString], output_path: Path) -> None:
    """Save extracted strings to a JSON file.

    Args:
        strings: Key -> `LocString`.
        output_path: JSON file to write.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {key: {"type": s.type, "desc": s.desc, "translations": s.translations, "source_file": s.source_file} for key, s in strings.items()}
    write_json(output_path, data)


def extract_mod(mod_id: str, mod_path: Path) -> ProgressDiff:
    """Re-extract a mod's strings into its `source.json` and update its progress.

    Args:
        mod_id: Mod's Workshop id.
        mod_path: Mod's folder.

    Returns:
        Which keys are new, modified, removed or unchanged since the last extraction.
    """
    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(mod_id, strings)
    save_extracted_strings(strings, GameStorage(GAME_ID).mod_file(mod_id, "source.json"))
    return ProgressTracker(game_id=GAME_ID).update(mod_id, strings, chrono_ark_adapter().source_languages)


def mod_detail(mod_id: str) -> dict:
    """Build the mod's metadata and one row per localization entry, refreshing its progress on the way.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Mod metadata plus a `strings` list (key, source text, target text, translation and sync status).
    """
    mod = _find_mod(mod_id)
    mod_path = mod.path
    storage = GameStorage(GAME_ID)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)

    # Exported gdata JSONs hold English now, so restore the original source text from backup.
    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)

    translations = load_translations(mod_id, game_id=GAME_ID)
    translation_providers = load_providers(mod_id, game_id=GAME_ID)

    # Must be captured before saved translations are applied below.
    original_english_map = {key: loc_str.translations.get(target_lang, "") for key, loc_str in strings.items()}

    synced_keys: set[str] = set(_read_json(storage.mod_file(mod_id, "synced_keys.json"), []))

    # If the mod author changed the CSVs since the last export, synced status is stale. Translation changes are intentionally ignored so
    # new translations don't invalidate synced rows.
    if synced_keys:
        csv_hash_path = storage.mod_file(mod_id, "last_csv_hash.json")
        if csv_hash_path.exists():
            if _compute_csv_snapshot(mod_path) != _read_json(csv_hash_path, {}).get("hash", ""):
                synced_keys = set()
        elif _compute_export_snapshot(mod_id, mod_path, mod.name) != _load_last_export_hash(mod_id):
            # No CSV hash saved yet, so fall back to the full snapshot check.
            synced_keys = set()

    # The CSV now holds the translated values, so the pre-export snapshot is needed to diff synced rows.
    pre_export_english: dict[str, str] = _read_json(storage.mod_file(mod_id, "pre_export_english.json"), {}) if synced_keys else {}

    # Saved translations win so user edits (including clears) are respected.
    for key, translated_text in translations.items():
        if key in strings:
            strings[key].translations[target_lang] = translated_text

    # With the Harmony injection mod, DLL strings become translatable, so clear their untranslatable_reason to count them in total_keys.
    if chrono_ark_adapter().get_translation_overrides_dir() is not None:
        for key, loc_str in strings.items():
            if key.startswith("DLL/") and loc_str.untranslatable_reason:
                loc_str.untranslatable_reason = ""

    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)
    lang_override = load_source_language_override(mod_id, game_id=GAME_ID)
    translated_keys = []
    results = []
    for key, loc_str in strings.items():
        source_lang = resolve_source_language(loc_str, lang_override)
        source_text = loc_str.translations.get(source_lang, "") if source_lang else ""
        target_text = loc_str.translations.get(target_lang, "")

        # No CJK source but target-language content (e.g. English-only gdata mods): treat the target as the source so the row shows in the UI.
        if not source_text and target_text:
            source_lang = target_lang
            source_text = target_text

        is_done = bool(target_text) or not source_text.strip()
        if source_text.strip() and bool(target_text):
            translated_keys.append(key)

        has_override = key in translations
        csv_target = original_english_map.get(key, "")
        is_synced = key in synced_keys
        is_untouched = bool(csv_target) and not has_override and not is_synced and target_text == csv_target
        results.append(
            {
                "key": key,
                "type": loc_str.type,
                "desc": loc_str.desc,
                "source": source_text,
                "source_lang": source_lang,
                "english": target_text,
                "is_translated": is_done,
                "original_english": pre_export_english.get(key, csv_target) if is_synced else csv_target,
                "is_synced": is_synced,
                "is_untouched": is_untouched,
                "synced_english": target_text if is_synced else "",
                "source_file": loc_str.source_file,
                "translated_by": translation_providers.get(key, ""),
                "untranslatable_reason": loc_str.untranslatable_reason,
            }
        )

    # Replace rather than add, so clears are reflected.
    tracker.set_translated(mod_id, translated_keys)

    preview_img = _find_mod_preview_image(mod_path)
    return {
        "id": mod_id,
        "name": mod.name,
        "author": mod.author,
        "url": chrono_ark_adapter().get_mod_url(mod_id),
        "preview_image": f"/workshop/{mod_id}/{preview_img.name}" if preview_img else None,
        "strings": results,
        "source_language_override": lang_override,
        "target_language_override": load_target_language_override(mod_id, game_id=GAME_ID),
    }


def export_mod(mod_id: str, resync: bool = False) -> dict:
    """Write saved translations into the mod's CSV/gdata files (or the Harmony override JSONs) and record an export snapshot.

    Args:
        mod_id: Mod's Workshop id.
        resync: Restore the original files from backup first, to re-apply on a clean base.

    Returns:
        `status`, `applied` count, and the files and overrides written.
    """
    mod = _find_mod(mod_id)
    mod_path = mod.path
    storage = GameStorage(GAME_ID)

    create_backup(mod_id, "Before re-sync export" if resync else "Before export", game_id=GAME_ID)

    if resync:
        _restore_originals(mod_id, mod_path)
    else:
        _back_up_originals(mod_id, mod_path)

    translations = load_translations(mod_id, game_id=GAME_ID)
    if not translations:
        raise DomainError("No translations found for this mod")

    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"
    strings, _ = chrono_ark_adapter().extract_strings(mod_path)

    # For the UI diff.
    pre_export_english = {key: loc_str.translations.get(target_lang, "") for key, loc_str in strings.items() if key in translations}

    applied = 0
    for key, translated_text in translations.items():
        if key in strings:
            strings[key].translations[target_lang] = translated_text
            applied += 1

    # With the Harmony injection mod, translations go to override JSONs instead of the original CSV/gdata files.
    overrides_dir = chrono_ark_adapter().get_translation_overrides_dir()
    files_written: list[str] = []
    gdata_files_written: list = []
    keyed_overrides: dict[str, str] = {}
    text_overrides: dict[str, str] = {}
    if overrides_dir:
        keyed_overrides, text_overrides = _override_entries(strings, translations, target_lang)
        # Override JSONs are grouped by mod name: { "ModName": { "key": "English", ... } }
        if keyed_overrides:
            _write_override(overrides_dir / "keyed_overrides.json", mod.name, keyed_overrides)
        if text_overrides:
            _write_override(overrides_dir / "text_overrides.json", mod.name, text_overrides)
    else:
        files_written, gdata_files_written = _write_mod_files(mod_path, strings, translations, target_lang)

    _save_last_export_hash(mod_id, _compute_export_snapshot(mod_id, mod_path, mod.name))
    # CSV-only hash, so synced-key invalidation triggers on mod-author CSV changes but not new user translations.
    write_json(storage.mod_file(mod_id, "last_csv_hash.json"), {"hash": _compute_csv_snapshot(mod_path)}, indent=None)
    write_json(storage.mod_file(mod_id, "synced_keys.json"), [k for k, v in translations.items() if v], indent=None)
    write_json(storage.mod_file(mod_id, "pre_export_english.json"), pre_export_english, indent=None)

    return {
        "status": "success",
        "applied": applied,
        "files_written": files_written,
        "gdata_files_written": gdata_files_written,
        "keyed_overrides_written": len(keyed_overrides),
        "text_overrides_written": len(text_overrides),
    }


def reset_mod(mod_id: str) -> dict:
    """Restore the pre-export CSV/gdata backups (if any), clean the Harmony overrides, and delete the mod's translation data.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status`, `csv_restored`, `gdata_restored`, and `overrides_cleared`.
    """
    mod_storage = GameStorage(GAME_ID).mod_dir(mod_id)
    if not mod_storage.exists():
        return {"status": "success", "csv_restored": False, "message": "No data to clear"}

    create_backup(mod_id, "Before reset", game_id=GAME_ID)

    has_originals = any((mod_storage / d).exists() for d in _RESET_DIRS)
    csv_restored, gdata_restored = _restore_originals(mod_id, _find_mod_path(mod_id)) if has_originals else (False, False)

    overrides_cleared = False
    overrides_dir = chrono_ark_adapter().get_translation_overrides_dir()
    if overrides_dir:
        mod_name = _find_mod(mod_id).name
        for json_name in ("keyed_overrides.json", "text_overrides.json"):
            overrides_cleared |= _write_override(overrides_dir / json_name, mod_name, None)

    for filename in _RESET_FILES:
        (mod_storage / filename).unlink(missing_ok=True)
    for dirname in _RESET_DIRS:
        if (mod_storage / dirname).exists():
            shutil.rmtree(mod_storage / dirname)

    return {"status": "success", "csv_restored": csv_restored, "gdata_restored": gdata_restored, "overrides_cleared": overrides_cleared}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Helpers


def _read_json(path: Path, default: Any) -> Any:
    """Read a sidecar JSON file.

    Args:
        path: File to read.
        default: Value for a missing or unreadable file.

    Returns:
        The parsed JSON, or `default`.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _back_up_originals(mod_id: str, mod_path: Path) -> None:
    """Copy the mod's CSVs and gdata JSONs into storage before its first export, so Reset can restore them.

    Args:
        mod_id: Mod's Workshop id.
        mod_path: Mod's folder.
    """
    mod_storage = GameStorage(GAME_ID).mod_dir(mod_id)
    original_csv_dir = mod_storage / "original_csvs"
    if not original_csv_dir.exists():
        original_csv_dir.mkdir(parents=True, exist_ok=True)
        for csv_path in _get_mod_csv_paths(mod_path):
            # Keeps the relative layout (Localization/file.csv vs file.csv).
            dest = original_csv_dir / csv_path.relative_to(mod_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(csv_path, dest)

    original_gdata_dir = mod_storage / "original_gdata"
    gdata_src = mod_path / "gdata" / "Add"
    if not original_gdata_dir.exists() and gdata_src.exists():
        original_gdata_dir.mkdir(parents=True, exist_ok=True)
        for json_path in gdata_src.glob("*.json"):
            shutil.copy2(json_path, original_gdata_dir / json_path.name)


def _restore_originals(mod_id: str, mod_path: Path) -> tuple[bool, bool]:
    """Copy the backed-up original CSVs and gdata JSONs back into the mod.

    Args:
        mod_id: Mod's Workshop id.
        mod_path: Mod's folder.

    Returns:
        (whether any CSV was restored, whether any gdata file was restored).
    """
    mod_storage = GameStorage(GAME_ID).mod_dir(mod_id)
    csv_restored = False
    original_csv_dir = mod_storage / "original_csvs"
    if original_csv_dir.exists():
        for src in original_csv_dir.rglob("*"):
            if src.is_file():
                dest = mod_path / src.relative_to(original_csv_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                csv_restored = True

    gdata_restored = False
    original_gdata_dir = mod_storage / "original_gdata"
    if original_gdata_dir.exists():
        gdata_dest = mod_path / "gdata" / "Add"
        gdata_dest.mkdir(parents=True, exist_ok=True)
        for src in original_gdata_dir.rglob("*"):
            if src.is_file():
                shutil.copy2(src, gdata_dest / src.name)
                gdata_restored = True
    return csv_restored, gdata_restored


def _write_mod_files(mod_path: Path, strings: dict[str, LocString], translations: dict[str, str], target_lang: str) -> tuple[list[str], list]:
    """Write the translated strings back into the mod's own CSVs and gdata JSONs.

    Args:
        mod_path: Mod's folder.
        strings: The mod's strings with translations applied.
        translations: Saved translations, which pick the keys to write.
        target_lang: Language the translations are in.

    Returns:
        (CSV file names written, gdata files written).
    """
    adapter = chrono_ark_adapter()
    gdata_translations: dict[str, str] = {}
    by_source: dict[str, list[LocString]] = {}
    for key, loc_str in strings.items():
        if loc_str.untranslatable_reason or key not in translations:
            continue
        source = loc_str.source_file or adapter.csv_for_key(loc_str.key)
        if source.lower().endswith(".json"):
            target_text = loc_str.translations.get(target_lang, "")
            if target_text:
                gdata_translations[key] = target_text
        else:
            if source.lower().endswith(".dll"):
                source = adapter.csv_for_key(loc_str.key)
            by_source.setdefault(source, []).append(loc_str)

    gdata_files_written = adapter.export_gdata_strings(mod_path, gdata_translations) if gdata_translations else []

    files_written = []
    for csv_filename, entries in by_source.items():
        loc_path = mod_path / "Localization" / csv_filename
        top_path = mod_path / csv_filename
        if loc_path.exists():
            output_path = loc_path
        elif top_path.exists():
            output_path = top_path
        else:
            (mod_path / "Localization").mkdir(parents=True, exist_ok=True)
            output_path = loc_path
        adapter.export_strings(output_path, entries)
        files_written.append(csv_filename)
    return files_written, gdata_files_written


def _override_entries(strings: dict[str, LocString], translations: dict[str, str], target_lang: str) -> tuple[dict[str, str], dict[str, str]]:
    """Split the translated strings into Harmony keyed overrides and DLL text overrides.

    Args:
        strings: The mod's strings with translations applied.
        translations: Saved translations, which pick the keys to write.
        target_lang: Language the translations are in.

    Returns:
        (key -> text overrides, source text -> text overrides for DLL strings).
    """
    keyed: dict[str, str] = {}
    text: dict[str, str] = {}
    for key, loc_str in strings.items():
        target_text = loc_str.translations.get(target_lang, "")
        if key not in translations or not target_text:
            continue
        if loc_str.source_file.lower().endswith(".dll"):
            t = loc_str.translations
            source = t.get("Chinese", "") or t.get("Chinese-TW [zh-tw]", "") or t.get("Japanese", "") or t.get("Korean", "")
            if source:
                text[source] = target_text
        elif key.startswith("Character/") and key.endswith("_Name"):
            # The game expects Character names as lowercase "_name" but gdata extraction produces "_Name".
            keyed[key[:-5] + "_name"] = target_text
        else:
            keyed[key] = target_text
    return keyed, text


def _write_override(path: Path, mod_name: str, entries: dict[str, str] | None) -> bool:
    """Set the mod's block in a Harmony override JSON, or remove it when `entries` is None.

    Args:
        path: Override JSON file.
        mod_name: Mod's display name, which keys its block.
        entries: The block to write, or None to remove it.

    Returns:
        Whether the file was written.
    """
    data = _read_json(path, {})
    if entries is None:
        if mod_name not in data:
            return False
        del data[mod_name]
    else:
        data[mod_name] = entries
    write_json(path, data)
    return True
