"""Chrono Ark mod API endpoints for the Steam Workshop Modding Dashboard."""

import json
import os
import shutil
import subprocess

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.core.json_store import write_json
from backend.core.paths import GameStorage, safe_child
from backend.data.character_context import load_character_context, save_character_context
from backend.data.history_manager import create_backup, delete_backup, list_backups, restore_backup
from backend.data.mod_settings import (
    load_source_language_override,
    load_target_language_override,
    save_source_language_override,
    save_target_language_override,
)
from backend.data.progress_tracker import ProgressTracker
from backend.data.translation_store import (
    clear_all_translations,
    load_translations,
    update_single_translation,
)
from backend.main import save_extracted_strings
from backend.routes.helpers import (
    _compute_csv_snapshot,
    _compute_export_snapshot,
    _find_mod,
    _find_mod_path,
    _find_mod_preview_image,
    _get_mod_csv_paths,
    _load_last_export_hash,
    _merge_gdata_originals,
    _recalculate_mod_progress,
    _save_last_export_hash,
    chrono_ark_adapter,
    resolve_source_language,
)
from backend.routes.models import CharacterContext, HistorySnapshotRequest, SourceLanguageOverride, TargetLanguageOverride, TranslationUpdate

router = APIRouter()


@router.get("/mods")
async def get_mods():
    """List all workshop mods with their translation status.

    Returns:
        One dict per mod: id, name, author, CSV/DLL flags, progress counters, workshop URL, preview image path.
    """
    mods = chrono_ark_adapter().scan_mods()
    tracker = ProgressTracker()

    results = []
    for mod in mods:
        status = tracker.get_status(mod.mod_id)
        preview_img = _find_mod_preview_image(mod.path)

        saved = load_translations(mod.mod_id)
        if saved:
            current_hash = _compute_export_snapshot(mod.mod_id, mod.path, mod.name)
            last_hash = _load_last_export_hash(mod.mod_id)
            has_changes = current_hash != last_hash
        else:
            has_changes = False

        user_translated = sum(1 for v in saved.values() if v)
        untouched = max(0, status["translated"] - user_translated)

        results.append(
            {
                "id": mod.mod_id,
                "name": mod.name,
                "author": mod.author,
                "has_csv": mod.has_loc_files,
                "has_dll": mod.has_dll,
                "total": status["total"],
                "translated": status["translated"],
                "untranslated": status["untranslated"],
                "user_translated": user_translated,
                "untouched": untouched,
                "percentage": status["percentage"],
                "last_updated": status["last_updated"],
                "url": chrono_ark_adapter().get_mod_url(mod.mod_id),
                "preview_image": f"/workshop/{mod.mod_id}/{preview_img.name}" if preview_img else None,
                "has_changes": has_changes,
            }
        )
    return results


@router.post("/mods/refresh")
async def refresh_mods(request: Request):
    """Rescan all mods and recalculate progress from disk, streaming a `progress` event (`current`/`total`/mod name) per mod.

    The final event carries the complete results list. The generator checks `request.is_disconnected` between mods so navigating away aborts early.

    Returns:
        `StreamingResponse` of `text/event-stream` events.
    """
    mods = chrono_ark_adapter().scan_mods()

    async def event_stream():
        tracker = ProgressTracker()
        results = []
        total = len(mods)

        for i, mod in enumerate(mods):
            if await request.is_disconnected():
                return

            _recalculate_mod_progress(mod.mod_id, mod.path)

            status = tracker.get_status(mod.mod_id)
            preview_img = _find_mod_preview_image(mod.path)

            saved = load_translations(mod.mod_id)
            if saved:
                current_hash = _compute_export_snapshot(mod.mod_id, mod.path, mod.name)
                last_hash = _load_last_export_hash(mod.mod_id)
                has_changes = current_hash != last_hash
            else:
                has_changes = False

            user_translated = sum(1 for v in saved.values() if v)
            untouched = max(0, status["translated"] - user_translated)

            mod_result = {
                "id": mod.mod_id,
                "name": mod.name,
                "author": mod.author,
                "has_csv": mod.has_loc_files,
                "has_dll": mod.has_dll,
                "total": status["total"],
                "translated": status["translated"],
                "untranslated": status["untranslated"],
                "user_translated": user_translated,
                "untouched": untouched,
                "percentage": status["percentage"],
                "last_updated": status["last_updated"],
                "url": chrono_ark_adapter().get_mod_url(mod.mod_id),
                "preview_image": f"/workshop/{mod.mod_id}/{preview_img.name}" if preview_img else None,
                "has_changes": has_changes,
            }
            results.append(mod_result)

            progress_event = {"current": i + 1, "total": total, "mod_name": mod.name}
            yield f"data: {json.dumps(progress_event)}\n\n"

        yield f"data: {json.dumps({'done': True, 'results': results})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/mods/{mod_id}")
async def get_mod_detail(mod_id: str):
    """Get a mod's metadata and every localization entry.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Mod metadata plus a `strings` list (key, source text, English text, translation status).
    """
    mod = _find_mod(mod_id)
    mod_path = mod.path

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)

    # Exported gdata JSONs hold English now, so restore the original source text from backup.
    target_lang = load_target_language_override(mod_id) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)

    translations = load_translations(mod_id)

    providers_path = GameStorage("chrono_ark").mod_file(mod_id, "translation_providers.json")
    translation_providers: dict[str, str] = {}
    if providers_path.exists():
        try:
            with open(providers_path, encoding="utf-8") as f:
                translation_providers = json.load(f)
        except Exception:
            pass

    # Must be captured before saved translations are applied below.
    original_english_map = {key: loc_str.translations.get(target_lang, "") for key, loc_str in strings.items()}

    synced_keys_path = GameStorage("chrono_ark").mod_file(mod_id, "synced_keys.json")
    synced_keys: set[str] = set()
    if synced_keys_path.exists():
        try:
            with open(synced_keys_path, encoding="utf-8") as f:
                synced_keys = set(json.load(f))
        except Exception:
            pass

    # If the mod author changed the CSVs since the last export, synced status is stale. Translation changes are intentionally ignored so
    # new translations don't invalidate synced rows.
    if synced_keys:
        csv_hash_path = GameStorage("chrono_ark").mod_file(mod_id, "last_csv_hash.json")
        if csv_hash_path.exists():
            try:
                with open(csv_hash_path, encoding="utf-8") as f:
                    last_csv_hash = json.load(f).get("hash", "")
            except Exception:
                last_csv_hash = ""
            if _compute_csv_snapshot(mod_path) != last_csv_hash:
                synced_keys = set()
        else:
            # No CSV hash saved yet, so fall back to the full snapshot check.
            current_hash = _compute_export_snapshot(mod_id, mod_path, mod.name)
            last_hash = _load_last_export_hash(mod_id)
            if current_hash != last_hash:
                synced_keys = set()

    # The CSV now holds the translated values, so the pre-export snapshot is needed to diff synced rows.
    pre_export_english: dict[str, str] = {}
    if synced_keys:
        pre_export_path = GameStorage("chrono_ark").mod_file(mod_id, "pre_export_english.json")
        if pre_export_path.exists():
            try:
                with open(pre_export_path, encoding="utf-8") as f:
                    pre_export_english = json.load(f)
            except Exception:
                pass

    # Saved translations win so user edits (including clears) are respected.
    for key, translated_text in translations.items():
        if key in strings:
            strings[key].translations[target_lang] = translated_text

    # With the Harmony injection mod, DLL strings become translatable, so clear their untranslatable_reason to count them in total_keys.
    has_harmony_mod = chrono_ark_adapter().get_translation_overrides_dir() is not None
    if has_harmony_mod:
        for key, loc_str in strings.items():
            if key.startswith("DLL/") and loc_str.untranslatable_reason:
                loc_str.untranslatable_reason = ""

    tracker = ProgressTracker()
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)
    lang_override = load_source_language_override(mod_id)
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
                "original_english": pre_export_english.get(key, original_english_map.get(key, "")) if is_synced else original_english_map.get(key, ""),
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
        "target_language_override": load_target_language_override(mod_id),
    }


@router.post("/mods/{mod_id}/strings")
async def update_string(mod_id: str, update: TranslationUpdate):
    """Save a manual translation for a specific key.

    Args:
        mod_id: Mod's Workshop id.
        update: Localization key and new English text.

    Returns:
        `{"status": "success"}`.
    """
    create_backup(mod_id, f"Before manual edit of '{update.key}'")
    update_single_translation(mod_id, update.key, update.english)

    providers_path = GameStorage("chrono_ark").mod_file(mod_id, "translation_providers.json")
    providers: dict[str, str] = {}
    if providers_path.exists():
        try:
            with open(providers_path, encoding="utf-8") as f:
                providers = json.load(f)
        except Exception:
            pass
    providers[update.key] = "manual"
    write_json(providers_path, providers)

    tracker = ProgressTracker()

    # An empty source keeps the key "translated" even with empty English.
    mods = chrono_ark_adapter().scan_mods()
    matching = [m for m in mods if m.mod_id == mod_id]
    if matching:
        strings, _ = chrono_ark_adapter().extract_strings(matching[0].path)
        if update.key in strings:
            loc_str = strings[update.key]
            lang_override = load_source_language_override(mod_id)
            source_lang = resolve_source_language(loc_str, lang_override)
            source_text = loc_str.translations.get(source_lang, "") if source_lang else ""

            is_done = bool(update.english) or not source_text.strip()
            if is_done:
                tracker.mark_translated(mod_id, [update.key])
            else:
                tracker.unmark_translated(mod_id, [update.key])

    return {"status": "success"}


@router.post("/mods/{mod_id}/sync")
async def sync_mod(mod_id: str):
    """Re-scan and extract strings for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status` and the `new`, `modified`, `removed`, `unchanged` key counts.
    """
    mod_path = _find_mod_path(mod_id)

    create_backup(mod_id, "Before sync")

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(mod_id, strings)
    output_path = GameStorage("chrono_ark").mod_file(mod_id, "source.json")
    save_extracted_strings(strings, output_path)

    tracker = ProgressTracker()
    diff = tracker.update(mod_id, strings, chrono_ark_adapter().source_languages)

    return {"status": "success", "new": len(diff.new_keys), "modified": len(diff.modified_keys), "removed": len(diff.removed_keys), "unchanged": len(diff.unchanged_keys)}


@router.post("/mods/{mod_id}/clear-translations")
async def clear_translations(mod_id: str):
    """Reset the mod to untranslated by writing empty-string overrides for every key that had English.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `{"status": "success"}`.
    """
    mod_path = _find_mod_path(mod_id)
    target_lang = load_target_language_override(mod_id) or "English"

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)

    create_backup(mod_id, "Before clearing translations")

    # Empty overrides stop the original CSV values showing through.
    keys_to_clear: list[str] = []
    for key, loc_str in strings.items():
        if loc_str.translations.get(target_lang, ""):
            keys_to_clear.append(key)

    existing = load_translations(mod_id)
    for key in existing:
        if key not in keys_to_clear:
            keys_to_clear.append(key)

    clear_all_translations(mod_id, keys_to_clear)

    for filename in ("synced_keys.json", "pre_export_english.json", "last_csv_hash.json"):
        path = GameStorage("chrono_ark").mod_file(mod_id, filename)
        if path.exists():
            path.unlink()

    tracker = ProgressTracker()
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)

    # Only keys with empty sources stay marked translated.
    lang_override = load_source_language_override(mod_id)
    done_keys = []
    for key, loc_str in strings.items():
        source_lang = resolve_source_language(loc_str, lang_override)
        source_text = loc_str.translations.get(source_lang, "") if source_lang else ""
        target_text = loc_str.translations.get(target_lang, "")
        if not source_text and target_text:
            source_text = target_text
        if not source_text.strip():
            done_keys.append(key)

    tracker.set_translated(mod_id, done_keys)

    return {"status": "success"}


@router.post("/mods/{mod_id}/reset")
async def reset_mod(mod_id: str):
    """Restore the pre-export CSV/gdata backups (if any), clean the Harmony overrides, and delete the mod's translation data.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status`, `csv_restored`, `gdata_restored`, and `overrides_cleared`.
    """
    mod_storage = GameStorage("chrono_ark").mod_dir(mod_id)
    if not mod_storage.exists():
        return {"status": "success", "csv_restored": False, "message": "No data to clear"}

    create_backup(mod_id, "Before reset")

    csv_restored = False
    original_csv_dir = mod_storage / "original_csvs"
    if original_csv_dir.exists():
        mod_path = _find_mod_path(mod_id)
        for src in original_csv_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(original_csv_dir)
                dest = mod_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                csv_restored = True

    gdata_restored = False
    original_gdata_dir = mod_storage / "original_gdata"
    if original_gdata_dir.exists():
        mod_path = _find_mod_path(mod_id)
        gdata_dest = mod_path / "gdata" / "Add"
        gdata_dest.mkdir(parents=True, exist_ok=True)
        for src in original_gdata_dir.rglob("*"):
            if src.is_file():
                shutil.copy2(src, gdata_dest / src.name)
                gdata_restored = True

    overrides_cleared = False
    overrides_dir = chrono_ark_adapter().get_translation_overrides_dir()
    if overrides_dir:
        mod_info = _find_mod(mod_id)
        mod_name = mod_info.name
        for json_name in ("keyed_overrides.json", "text_overrides.json"):
            json_path = overrides_dir / json_name
            if not json_path.exists():
                continue
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if mod_name in data:
                del data[mod_name]
                write_json(json_path, data)
                overrides_cleared = True

    # Only translation data is deleted so user-configured data (character context, glossary) survives.
    files_to_delete = [
        "translations.json",
        "progress.json",
        "synced_keys.json",
        "last_export.json",
        "last_csv_hash.json",
        "pre_export_english.json",
        "last_api_responses.json",
    ]
    dirs_to_delete = ["original_csvs", "original_gdata"]

    try:
        for filename in files_to_delete:
            path = mod_storage / filename
            if path.exists():
                path.unlink()
        for dirname in dirs_to_delete:
            path = mod_storage / dirname
            if path.exists():
                shutil.rmtree(path)
        return {
            "status": "success",
            "csv_restored": csv_restored,
            "gdata_restored": gdata_restored,
            "overrides_cleared": overrides_cleared,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}") from e


@router.post("/mods/{mod_id}/open")
async def open_mod_folder(mod_id: str):
    """Open the mod's directory in the system file explorer.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `{"status": "success"}`.
    """
    mod_path = _find_mod_path(mod_id)
    if not mod_path.exists():
        raise HTTPException(status_code=404, detail="Mod directory not found")

    try:
        os.startfile(mod_path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}") from e


@router.get("/mods/{mod_id}/export-status")
async def get_export_status(mod_id: str):
    """Check whether translation/CSV state differs from the last export snapshot.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `has_changes` and `has_previous_sync` flags.
    """
    mod = _find_mod(mod_id)

    translations = load_translations(mod_id)
    if not translations:
        return {"has_changes": False}

    current_hash = _compute_export_snapshot(mod_id, mod.path, mod.name)
    last_hash = _load_last_export_hash(mod_id)

    return {
        "has_changes": current_hash != last_hash,
        "has_previous_sync": last_hash != "",
    }


@router.post("/mods/{mod_id}/export")
async def export_mod(mod_id: str, resync: bool = False):
    """Write saved translations into the mod's CSV/gdata files (or the Harmony override JSONs) and record an export snapshot.

    Args:
        mod_id: Mod's Workshop id.
        resync: Restore the original files from backup first, to re-apply on a clean base.

    Returns:
        `status`, `applied` count, and the files and overrides written.
    """
    mod = _find_mod(mod_id)
    mod_path = mod.path

    reason = "Before re-sync export" if resync else "Before export"
    create_backup(mod_id, reason)

    original_csv_dir = GameStorage("chrono_ark").mod_dir(mod_id) / "original_csvs"
    original_gdata_dir = GameStorage("chrono_ark").mod_dir(mod_id) / "original_gdata"

    if resync:
        if original_csv_dir.exists():
            for src in original_csv_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(original_csv_dir)
                    dest = mod_path / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

        if original_gdata_dir.exists():
            gdata_dest = mod_path / "gdata" / "Add"
            gdata_dest.mkdir(parents=True, exist_ok=True)
            for src in original_gdata_dir.rglob("*"):
                if src.is_file():
                    shutil.copy2(src, gdata_dest / src.name)
    else:
        # Back up the originals before the first export so "Reset" can restore them.
        if not original_csv_dir.exists():
            original_csv_dir.mkdir(parents=True, exist_ok=True)
            for csv_path in _get_mod_csv_paths(mod_path):
                # Keeps the relative layout (Localization/file.csv vs file.csv).
                rel = csv_path.relative_to(mod_path)
                dest = original_csv_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(csv_path, dest)

        gdata_src = mod_path / "gdata" / "Add"
        if not original_gdata_dir.exists() and gdata_src.exists():
            original_gdata_dir.mkdir(parents=True, exist_ok=True)
            for json_path in gdata_src.glob("*.json"):
                shutil.copy2(json_path, original_gdata_dir / json_path.name)

    translations = load_translations(mod_id)
    if not translations:
        raise HTTPException(status_code=400, detail="No translations found for this mod")

    target_lang = load_target_language_override(mod_id) or "English"

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

    files_written = []
    gdata_files_written = []

    if not overrides_dir:
        gdata_translations: dict[str, str] = {}
        by_source: dict[str, list] = {}
        for key, loc_str in strings.items():
            if loc_str.untranslatable_reason:
                continue
            if key not in translations:
                continue
            source = loc_str.source_file or chrono_ark_adapter().csv_for_key(loc_str.key)
            if source.lower().endswith(".json"):
                target_text = loc_str.translations.get(target_lang, "")
                if target_text:
                    gdata_translations[key] = target_text
            else:
                if source.lower().endswith(".dll"):
                    source = chrono_ark_adapter().csv_for_key(loc_str.key)
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(loc_str)

        if gdata_translations:
            gdata_files_written = chrono_ark_adapter().export_gdata_strings(mod_path, gdata_translations)

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

            chrono_ark_adapter().export_strings(output_path, entries)
            files_written.append(csv_filename)

    # Override JSONs are grouped by mod name: { "ModName": { "key": "English", ... } }
    keyed_overrides_written = 0
    text_overrides_written = 0
    if overrides_dir:
        mod_name = mod.name

        keyed_overrides: dict[str, str] = {}
        text_overrides: dict[str, str] = {}

        for key, loc_str in strings.items():
            if key not in translations:
                continue
            target_text = loc_str.translations.get(target_lang, "")
            if not target_text:
                continue

            if loc_str.source_file.lower().endswith(".dll"):
                source = (
                    loc_str.translations.get("Chinese", "") or loc_str.translations.get("Chinese-TW [zh-tw]", "") or loc_str.translations.get("Japanese", "") or loc_str.translations.get("Korean", "")
                )
                if source:
                    text_overrides[source] = target_text
            else:
                # The game expects Character names as lowercase "_name" but gdata extraction produces "_Name".
                override_key = key
                if key.startswith("Character/") and key.endswith("_Name"):
                    override_key = key[:-5] + "_name"
                keyed_overrides[override_key] = target_text

        if keyed_overrides:
            keyed_path = overrides_dir / "keyed_overrides.json"
            existing: dict = {}
            if keyed_path.exists():
                try:
                    with open(keyed_path, encoding="utf-8") as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            existing[mod_name] = keyed_overrides
            write_json(keyed_path, existing)
            keyed_overrides_written = len(keyed_overrides)

        if text_overrides:
            text_path = overrides_dir / "text_overrides.json"
            existing = {}
            if text_path.exists():
                try:
                    with open(text_path, encoding="utf-8") as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            existing[mod_name] = text_overrides
            write_json(text_path, existing)
            text_overrides_written = len(text_overrides)

    snapshot_hash = _compute_export_snapshot(mod_id, mod_path, mod.name)
    _save_last_export_hash(mod_id, snapshot_hash)

    # CSV-only hash, so synced-key invalidation triggers on mod-author CSV changes but not new user translations.
    csv_hash_path = GameStorage("chrono_ark").mod_file(mod_id, "last_csv_hash.json")
    write_json(csv_hash_path, {"hash": _compute_csv_snapshot(mod_path)}, indent=None)

    synced_keys_path = GameStorage("chrono_ark").mod_file(mod_id, "synced_keys.json")
    synced_keys_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(synced_keys_path, [k for k, v in translations.items() if v], indent=None)

    pre_export_path = GameStorage("chrono_ark").mod_file(mod_id, "pre_export_english.json")
    write_json(pre_export_path, pre_export_english, indent=None)

    return {
        "status": "success",
        "applied": applied,
        "files_written": files_written,
        "gdata_files_written": gdata_files_written,
        "keyed_overrides_written": keyed_overrides_written,
        "text_overrides_written": text_overrides_written,
    }


@router.post("/mods/{mod_id}/open-source-file/{filename}")
async def open_source_file(mod_id: str, filename: str):
    """Open a mod's source file (searched in Localization/, gdata/Add/, then the mod root) in the OS default application.

    Args:
        mod_id: Mod's Workshop id.
        filename: Source filename (e.g. `LangDataDB.csv`, `B_Roland_Rare_S.json`).

    Returns:
        `{"path": resolved file path}`.
    """
    mod_path = _find_mod_path(mod_id)

    candidates = [
        mod_path / "Localization" / filename,
        mod_path / "gdata" / "Add" / filename,
        mod_path / filename,
    ]

    for candidate in candidates:
        if candidate.is_file():
            os.startfile(candidate)
            return {"path": str(candidate)}

    raise HTTPException(status_code=404, detail=f"Source file not found: {filename}")


@router.post("/open-base-game-file/{filename}")
async def open_base_game_file(filename: str):
    """Open Explorer on the base game source file with it selected.

    Args:
        filename: Source filename (e.g. `LangDataDB.csv`).

    Returns:
        `{"path": resolved file path}`.
    """
    base_path = chrono_ark_adapter().base_game_path
    if base_path is None:
        raise HTTPException(status_code=400, detail="Base game path not configured")

    try:
        candidate = safe_child(base_path, filename)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Base game file not found: {filename}") from None
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Base game file not found: {filename}")

    subprocess.Popen(["explorer", "/select,", str(candidate)])
    return {"path": str(candidate)}


@router.get("/mods/{mod_id}/character-context")
async def get_character_context(mod_id: str):
    """Return saved character context for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `source_game`, `character_name`, and `background` strings (possibly empty).
    """
    return load_character_context(mod_id)


@router.post("/mods/{mod_id}/character-context")
async def set_character_context(mod_id: str, ctx: CharacterContext):
    """Save character context for a mod.

    Args:
        mod_id: Mod's Workshop id.
        ctx: Character context to persist.

    Returns:
        `{"status": "saved"}`.
    """
    create_backup(mod_id, "Before updating character context")
    save_character_context(mod_id, ctx.model_dump())
    return {"status": "saved"}


@router.get("/mods/{mod_id}/source-language")
async def get_source_language(mod_id: str):
    """Return the source language override for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `source_language` override name, or None when auto-detecting.
    """
    return {"source_language": load_source_language_override(mod_id)}


@router.post("/mods/{mod_id}/source-language")
async def set_source_language(mod_id: str, body: SourceLanguageOverride):
    """Save a source language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        body: Payload with `source_language`.

    Returns:
        `{"status": "saved"}`.
    """
    save_source_language_override(mod_id, body.source_language)
    return {"status": "saved"}


@router.get("/mods/{mod_id}/target-language")
async def get_target_language(mod_id: str):
    """Return the target language override for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `target_language` override name, or None for the English default.
    """
    return {"target_language": load_target_language_override(mod_id)}


@router.post("/mods/{mod_id}/target-language")
async def set_target_language(mod_id: str, body: TargetLanguageOverride):
    """Save a target language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        body: Payload with `target_language`.

    Returns:
        `{"status": "saved"}`.
    """
    save_target_language_override(mod_id, body.target_language)
    return {"status": "saved"}


@router.get("/mods/{mod_id}/history")
async def get_history(mod_id: str):
    """List a mod's backup snapshots, newest first.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Backup dicts with id, reason, created_at, and files.
    """
    return list_backups(mod_id)


@router.post("/mods/{mod_id}/history")
async def create_history_snapshot(mod_id: str, body: HistorySnapshotRequest):
    """Create a manual save-snapshot of the mod's current state.

    Args:
        mod_id: Mod's Workshop id.
        body: Snapshot request with an optional label.

    Returns:
        `{"status": "saved", "id": backup_id}`, or `{"status": "empty"}` when there was nothing to back up.
    """
    backup_id = create_backup(mod_id, body.label.strip() or "Manual snapshot", kind="manual")
    if backup_id is None:
        return {"status": "empty"}
    return {"status": "saved", "id": backup_id}


@router.post("/mods/{mod_id}/history/{backup_id}/restore")
async def restore_history(mod_id: str, backup_id: str):
    """Restore a mod's state from a backup snapshot, backing up the current state first.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Timestamp id of the backup.

    Returns:
        `{"status": "success"}`.
    """
    if not restore_backup(mod_id, backup_id):
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"status": "success"}


@router.delete("/mods/{mod_id}/history/{backup_id}")
async def delete_history(mod_id: str, backup_id: str):
    """Delete a specific backup snapshot.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Timestamp id of the backup.

    Returns:
        `{"status": "success"}`.
    """
    delete_backup(mod_id, backup_id)
    return {"status": "success"}


@router.get("/mods/{mod_id}/api-responses")
async def get_api_responses(mod_id: str):
    """Get the raw API responses from the last translation run.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Response dicts with batch_index, model, input_tokens, output_tokens, and raw_text.
    """
    responses_path = GameStorage("chrono_ark").mod_file(mod_id, "last_api_responses.json")
    if not responses_path.exists():
        return []
    with open(responses_path, encoding="utf-8") as f:
        return json.load(f)
