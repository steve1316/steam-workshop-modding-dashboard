"""Chrono Ark mod API endpoints for the Steam Workshop Modding Dashboard."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.core.os_open import open_path, reveal_path
from backend.core.paths import GameStorage, safe_child
from backend.games.base import ModInfo
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.services import mods as mod_services
from backend.models.api import CharacterContext, HistorySnapshotRequest, SourceLanguageOverride, TargetLanguageOverride, TranslationUpdate
from backend.persistence import api_response_log
from backend.persistence.character_context import load_character_context, save_character_context
from backend.persistence.history_manager import create_backup, delete_backup, list_backups, restore_backup
from backend.persistence.mod_settings import (
    load_source_language_override,
    load_target_language_override,
    save_source_language_override,
    save_target_language_override,
)
from backend.persistence.progress_tracker import ProgressTracker
from backend.persistence.translation_store import (
    clear_all_translations,
    load_translations,
    update_single_translation,
)
from backend.routes.helpers import (
    _compute_export_snapshot,
    _find_mod,
    _find_mod_path,
    _find_mod_preview_image,
    _load_last_export_hash,
    _recalculate_mod_progress,
    chrono_ark_adapter,
    resolve_source_language,
)

router = APIRouter()


@router.get("/mods")
def get_mods():
    """List all workshop mods with their translation status.

    Returns:
        One dict per mod: id, name, author, CSV/DLL flags, progress counters, workshop URL, preview image path.
    """
    mods = chrono_ark_adapter().scan_mods()
    tracker = ProgressTracker(game_id=GAME_ID)

    results = []
    for mod in mods:
        status = tracker.get_status(mod.mod_id)
        preview_img = _find_mod_preview_image(mod.path)

        saved = load_translations(mod.mod_id, game_id=GAME_ID)
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


def _refresh_mod(mod: ModInfo, tracker: ProgressTracker) -> dict:
    """Recalculate one mod's progress from disk and build its row for the mods table.

    Args:
        mod: The mod.
        tracker: Progress tracker shared across the refresh.

    Returns:
        The mod's summary row.
    """
    _recalculate_mod_progress(mod.mod_id, mod.path)
    status = tracker.get_status(mod.mod_id)
    preview_img = _find_mod_preview_image(mod.path)

    saved = load_translations(mod.mod_id, game_id=GAME_ID)
    has_changes = bool(saved) and _compute_export_snapshot(mod.mod_id, mod.path, mod.name) != _load_last_export_hash(mod.mod_id)
    user_translated = sum(1 for v in saved.values() if v)

    return {
        "id": mod.mod_id,
        "name": mod.name,
        "author": mod.author,
        "has_csv": mod.has_loc_files,
        "has_dll": mod.has_dll,
        "total": status["total"],
        "translated": status["translated"],
        "untranslated": status["untranslated"],
        "user_translated": user_translated,
        "untouched": max(0, status["translated"] - user_translated),
        "percentage": status["percentage"],
        "last_updated": status["last_updated"],
        "url": chrono_ark_adapter().get_mod_url(mod.mod_id),
        "preview_image": f"/workshop/{mod.mod_id}/{preview_img.name}" if preview_img else None,
        "has_changes": has_changes,
    }


@router.post("/mods/refresh")
async def refresh_mods(request: Request):
    """Rescan all mods and recalculate progress from disk, streaming a `progress` event (`current`/`total`/mod name) per mod.

    The final event carries the complete results list. The generator checks `request.is_disconnected` between mods so navigating away aborts early.

    Returns:
        `StreamingResponse` of `text/event-stream` events.
    """
    mods = await asyncio.to_thread(chrono_ark_adapter().scan_mods)

    async def event_stream():
        tracker = ProgressTracker(game_id=GAME_ID)
        results = []
        total = len(mods)

        for i, mod in enumerate(mods):
            if await request.is_disconnected():
                return

            results.append(await asyncio.to_thread(_refresh_mod, mod, tracker))

            progress_event = {"current": i + 1, "total": total, "mod_name": mod.name}
            yield f"data: {json.dumps(progress_event)}\n\n"

        yield f"data: {json.dumps({'done': True, 'results': results})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/mods/{mod_id}")
def get_mod_detail(mod_id: str):
    """Get a mod's metadata and every localization entry.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Mod metadata plus a `strings` list (key, source text, English text, translation status).
    """
    return mod_services.mod_detail(mod_id)


@router.post("/mods/{mod_id}/strings")
def update_string(mod_id: str, update: TranslationUpdate):
    """Save a manual translation for a specific key.

    Args:
        mod_id: Mod's Workshop id.
        update: Localization key and new English text.

    Returns:
        `{"status": "success"}`.
    """
    create_backup(mod_id, f"Before manual edit of '{update.key}'", game_id=GAME_ID)
    update_single_translation(mod_id, update.key, update.english, game_id=GAME_ID, provider="manual")

    tracker = ProgressTracker(game_id=GAME_ID)

    # An empty source keeps the key "translated" even with empty English.
    mod = chrono_ark_adapter().find_mod(mod_id)
    if mod is not None:
        strings, _ = chrono_ark_adapter().extract_strings(mod.path)
        if update.key in strings:
            loc_str = strings[update.key]
            lang_override = load_source_language_override(mod_id, game_id=GAME_ID)
            source_lang = resolve_source_language(loc_str, lang_override)
            source_text = loc_str.translations.get(source_lang, "") if source_lang else ""

            is_done = bool(update.english) or not source_text.strip()
            if is_done:
                tracker.mark_translated(mod_id, [update.key])
            else:
                tracker.unmark_translated(mod_id, [update.key])

    return {"status": "success"}


@router.post("/mods/{mod_id}/sync")
def sync_mod(mod_id: str):
    """Re-scan and extract strings for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status` and the `new`, `modified`, `removed`, `unchanged` key counts.
    """
    mod_path = _find_mod_path(mod_id)
    create_backup(mod_id, "Before sync", game_id=GAME_ID)
    diff = mod_services.extract_mod(mod_id, mod_path)
    return {"status": "success", "new": len(diff.new_keys), "modified": len(diff.modified_keys), "removed": len(diff.removed_keys), "unchanged": len(diff.unchanged_keys)}


@router.post("/mods/{mod_id}/clear-translations")
def clear_translations(mod_id: str):
    """Reset the mod to untranslated by writing empty-string overrides for every key that had English.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `{"status": "success"}`.
    """
    mod_path = _find_mod_path(mod_id)
    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)

    create_backup(mod_id, "Before clearing translations", game_id=GAME_ID)

    # Empty overrides stop the original CSV values showing through.
    keys_to_clear: list[str] = []
    for key, loc_str in strings.items():
        if loc_str.translations.get(target_lang, ""):
            keys_to_clear.append(key)

    existing = load_translations(mod_id, game_id=GAME_ID)
    for key in existing:
        if key not in keys_to_clear:
            keys_to_clear.append(key)

    clear_all_translations(mod_id, keys_to_clear, game_id=GAME_ID)

    for filename in ("synced_keys.json", "pre_export_english.json", "last_csv_hash.json"):
        path = GameStorage(GAME_ID).mod_file(mod_id, filename)
        if path.exists():
            path.unlink()

    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.update(mod_id, strings, chrono_ark_adapter().source_languages, target_lang=target_lang)

    # Only keys with empty sources stay marked translated.
    lang_override = load_source_language_override(mod_id, game_id=GAME_ID)
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
def reset_mod(mod_id: str):
    """Restore the pre-export CSV/gdata backups (if any), clean the Harmony overrides, and delete the mod's translation data.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status`, `csv_restored`, `gdata_restored`, and `overrides_cleared`.
    """
    try:
        return mod_services.reset_mod(mod_id)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset: {e}") from e


@router.post("/mods/{mod_id}/open")
def open_mod_folder(mod_id: str):
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
        open_path(mod_path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}") from e


@router.get("/mods/{mod_id}/export-status")
def get_export_status(mod_id: str):
    """Check whether translation/CSV state differs from the last export snapshot.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `has_changes` and `has_previous_sync` flags.
    """
    mod = _find_mod(mod_id)

    translations = load_translations(mod_id, game_id=GAME_ID)
    if not translations:
        return {"has_changes": False}

    current_hash = _compute_export_snapshot(mod_id, mod.path, mod.name)
    last_hash = _load_last_export_hash(mod_id)

    return {
        "has_changes": current_hash != last_hash,
        "has_previous_sync": last_hash != "",
    }


@router.post("/mods/{mod_id}/export")
def export_mod(mod_id: str, resync: bool = False):
    """Write saved translations into the mod's CSV/gdata files (or the Harmony override JSONs) and record an export snapshot.

    Args:
        mod_id: Mod's Workshop id.
        resync: Restore the original files from backup first, to re-apply on a clean base.

    Returns:
        `status`, `applied` count, and the files and overrides written.
    """
    return mod_services.export_mod(mod_id, resync=resync)


@router.post("/mods/{mod_id}/open-source-file/{filename}")
def open_source_file(mod_id: str, filename: str):
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
            open_path(candidate)
            return {"path": str(candidate)}

    raise HTTPException(status_code=404, detail=f"Source file not found: {filename}")


@router.post("/open-base-game-file/{filename}")
def open_base_game_file(filename: str):
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

    reveal_path(candidate)
    return {"path": str(candidate)}


@router.get("/mods/{mod_id}/character-context")
def get_character_context(mod_id: str):
    """Return saved character context for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `source_game`, `character_name`, and `background` strings (possibly empty).
    """
    return load_character_context(mod_id, game_id=GAME_ID)


@router.post("/mods/{mod_id}/character-context")
def set_character_context(mod_id: str, ctx: CharacterContext):
    """Save character context for a mod.

    Args:
        mod_id: Mod's Workshop id.
        ctx: Character context to persist.

    Returns:
        `{"status": "saved"}`.
    """
    create_backup(mod_id, "Before updating character context", game_id=GAME_ID)
    save_character_context(mod_id, ctx.model_dump(), game_id=GAME_ID)
    return {"status": "saved"}


@router.get("/mods/{mod_id}/source-language")
def get_source_language(mod_id: str):
    """Return the source language override for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `source_language` override name, or None when auto-detecting.
    """
    return {"source_language": load_source_language_override(mod_id, game_id=GAME_ID)}


@router.post("/mods/{mod_id}/source-language")
def set_source_language(mod_id: str, body: SourceLanguageOverride):
    """Save a source language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        body: Payload with `source_language`.

    Returns:
        `{"status": "saved"}`.
    """
    save_source_language_override(mod_id, body.source_language, game_id=GAME_ID)
    return {"status": "saved"}


@router.get("/mods/{mod_id}/target-language")
def get_target_language(mod_id: str):
    """Return the target language override for a mod.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `target_language` override name, or None for the English default.
    """
    return {"target_language": load_target_language_override(mod_id, game_id=GAME_ID)}


@router.post("/mods/{mod_id}/target-language")
def set_target_language(mod_id: str, body: TargetLanguageOverride):
    """Save a target language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        body: Payload with `target_language`.

    Returns:
        `{"status": "saved"}`.
    """
    save_target_language_override(mod_id, body.target_language, game_id=GAME_ID)
    return {"status": "saved"}


@router.get("/mods/{mod_id}/history")
def get_history(mod_id: str):
    """List a mod's backup snapshots, newest first.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Backup dicts with id, reason, created_at, and files.
    """
    return list_backups(mod_id, game_id=GAME_ID)


@router.post("/mods/{mod_id}/history")
def create_history_snapshot(mod_id: str, body: HistorySnapshotRequest):
    """Create a manual save-snapshot of the mod's current state.

    Args:
        mod_id: Mod's Workshop id.
        body: Snapshot request with an optional label.

    Returns:
        `{"status": "saved", "id": backup_id}`, or `{"status": "empty"}` when there was nothing to back up.
    """
    backup_id = create_backup(mod_id, body.label.strip() or "Manual snapshot", kind="manual", game_id=GAME_ID)
    if backup_id is None:
        return {"status": "empty"}
    return {"status": "saved", "id": backup_id}


@router.post("/mods/{mod_id}/history/{backup_id}/restore")
def restore_history(mod_id: str, backup_id: str):
    """Restore a mod's state from a backup snapshot, backing up the current state first.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Timestamp id of the backup.

    Returns:
        `{"status": "success"}`.
    """
    if not restore_backup(mod_id, backup_id, game_id=GAME_ID):
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"status": "success"}


@router.delete("/mods/{mod_id}/history/{backup_id}")
def delete_history(mod_id: str, backup_id: str):
    """Delete a specific backup snapshot.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Timestamp id of the backup.

    Returns:
        `{"status": "success"}`.
    """
    delete_backup(mod_id, backup_id, game_id=GAME_ID)
    return {"status": "success"}


@router.get("/mods/{mod_id}/api-responses")
def get_api_responses(mod_id: str):
    """List a mod's API call entries, newest first.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Log entries with `timestamp`, `kind`, `provider`, `model`, token counts, `cost_usd`, `keys_or_inputs` and `raw_response`.
    """
    return api_response_log.list_entries(mod_id, game_id=GAME_ID)
