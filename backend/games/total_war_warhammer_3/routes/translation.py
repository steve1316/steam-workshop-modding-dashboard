"""REST endpoints for the WH3 translation pipeline, mounted under `/api/games/total_war_warhammer_3/translation`.

Heavy I/O (RPFM extract, TSV scan) sits behind module-level helpers so tests can monkeypatch them.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.core.os_open import open_path
from backend.core.settings import settings
from backend.data import api_response_log, character_context, history_manager, mod_settings, translation_store
from backend.data.mod_settings import (
    load_source_language_override,
    load_target_language_override,
    save_source_language_override,
    save_target_language_override,
)
from backend.games.total_war_warhammer_3 import GAME_ID
from backend.games.total_war_warhammer_3.loc.extractor import (
    LocRow,
    extract_parent_pack_strings,
    normalize_loc_filename,
    read_translation_loc_tsv,
)
from backend.games.total_war_warhammer_3.loc.packer import (
    PackBuildError,
    RpfmNotConfiguredError,
    build_translation_pack,
)
from backend.games.total_war_warhammer_3.loc.writeback import _find_existing_user_file, remove_keys_from_loc_tsv, sync_translations_to_loc_tsv, user_loc_tsv_files
from backend.games.total_war_warhammer_3.paths import parent_pack_cache_dir, resolve_rpfm_cli_path, rpfm_cli_candidate, tw3_workshop_content_dir
from backend.games.total_war_warhammer_3.stores import glossary as glossary_store
from backend.games.total_war_warhammer_3.translation.canonical_status import to_status_rows
from backend.games.total_war_warhammer_3.translation.drift import (
    DriftRow,
    compute_drift,
)
from backend.games.total_war_warhammer_3.translation.mods import (
    WH3_TRANSLATION_MODS,
    WH3TranslationMod,
    get_translation_mod,
)
from backend.games.total_war_warhammer_3.translation.source_snapshot import accept_keys, load_parent_snapshot, refresh_unchanged, save_parent_snapshot
from backend.games.total_war_warhammer_3.workshop import change_notes as tcn
from backend.translation.rename import rename_term

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translation", tags=["translation"])


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Helpers (extracted as module-level functions so tests can monkeypatch them)


def _extract_translation_strings(mod: WH3TranslationMod) -> dict[str, dict[str, LocRow]]:
    """Read all `.loc.tsv` files under `mod.local_source_dir/text/**`.

    Args:
        mod: Translation mod whose local source dir to scan.

    Returns:
        Normalized filename to `{key: LocRow}`.
    """
    out: dict[str, dict[str, LocRow]] = {}
    text_dir = mod.local_source_dir / "text"
    if not text_dir.exists():
        return out
    for tsv in text_dir.rglob("*.loc.tsv"):
        norm = normalize_loc_filename(tsv.name)
        out[norm] = read_translation_loc_tsv(tsv)
    return out


def _extract_all_parent_strings(mod: WH3TranslationMod) -> dict[str, dict[str, LocRow]]:
    """Extract `.loc` strings from every parent `.pack` declared on `mod`.

    Args:
        mod: Translation mod whose parent packs to extract.

    Returns:
        Normalized filename to `{key: LocRow}`, merged across all parents.
    """
    rpfm = resolve_rpfm_cli_path()
    if rpfm is None:
        tried = rpfm_cli_candidate(settings.tw3.rpfm_cli_path or "", settings.tw3.helper_path or "") or "SWMT_TW3_RPFM_CLI_PATH"
        raise HTTPException(500, f"rpfm_cli not found (tried {tried}); set SWMT_TW3_RPFM_CLI_PATH or place rpfm_cli.exe in SWMT_TW3_HELPER_PATH")

    merged: dict[str, dict[str, LocRow]] = {}
    for parent_id in mod.parent_workshop_ids:
        parent_dir = tw3_workshop_content_dir(parent_id)
        if parent_dir is None:
            raise HTTPException(500, "TW3 Steam library drive is not configured")
        if not parent_dir.exists():
            continue
        packs = sorted(parent_dir.glob("*.pack"))
        if not packs:
            continue
        cache_dir = parent_pack_cache_dir(parent_id)
        for pack in packs:
            extracted = extract_parent_pack_strings(pack, rpfm, cache_dir)
            for filename, rows in extracted.items():
                merged.setdefault(filename, {}).update(rows)
    return merged


def _require_mod(mod_id: str) -> WH3TranslationMod:
    """Look up a mod by id or raise 404.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        The matching `WH3TranslationMod`.
    """
    mod = get_translation_mod(mod_id)
    if mod is None:
        raise HTTPException(404, f"WH3 translation mod {mod_id} not registered")
    return mod


def _backup(mod: WH3TranslationMod, label: str, *, kind: str = "auto") -> str | None:
    """Back up a mod's state, including its local `.loc.tsv` files.

    Args:
        mod: Translation mod to back up.
        label: Reason shown in History.
        kind: "auto" before destructive ops, "manual" for user saves.

    Returns:
        The backup id, or None if there was nothing to back up.
    """
    return history_manager.create_backup(mod.workshop_id, label, game_id=GAME_ID, kind=kind, extra_files=user_loc_tsv_files(mod))


def _serialize_drift_row(row: DriftRow) -> dict:
    """Convert a `DriftRow` to a JSON-serializable dict.

    Args:
        row: Drift row to serialize.

    Returns:
        Dict with `source_filename`, `key`, `parent_text`, `translation_text`, `status` and `provider`.
    """
    return {
        "source_filename": row.source_filename,
        "key": row.key,
        "parent_text": row.parent_text,
        "translation_text": row.translation_text,
        "status": row.status,
        "provider": row.provider,
    }


def _overlay_translations(drift: list[DriftRow], raw_translations: dict) -> list[DriftRow]:
    """Overlay `translations.json` onto computed drift rows so in-flight edits and clears show immediately.

    A non-empty override supplies its text/provider and promotes an untranslated row to `translated`. An empty-string override is an explicit clear,
    so the row shows empty text and is `untranslated` (when it has parent text) rather than the `.loc.tsv` content. Rows with no override keep their
    `.loc.tsv` status, with `provider` `manual` when text is present and `None` otherwise.
    `get_strings` and `rescan` both use this so the table and counts agree.

    Args:
        drift: Rows from `compute_drift`.
        raw_translations: The mod's `translations.json` (`key -> {text, provider}`).

    Returns:
        New `DriftRow` list with overrides applied, in input order.
    """
    overlaid: list[DriftRow] = []
    for row in drift:
        entry = raw_translations.get(row.key) or {}
        has_override = isinstance(entry, dict) and "text" in entry
        if has_override and entry["text"]:
            override_provider = entry.get("provider") or "manual"
            # Present in translations.json but untranslated on disk, so promote it.
            new_status = "translated" if row.status == "untranslated" else row.status
            overlaid.append(
                DriftRow(
                    source_filename=row.source_filename,
                    key=row.key,
                    parent_text=row.parent_text,
                    translation_text=entry["text"],
                    status=new_status,
                    provider=override_provider,
                )
            )
        elif has_override:
            # Explicit clear: show empty and mark untranslated so the .loc.tsv content does not show through.
            cleared_status = "untranslated" if row.parent_text is not None else row.status
            overlaid.append(
                DriftRow(
                    source_filename=row.source_filename,
                    key=row.key,
                    parent_text=row.parent_text,
                    translation_text="",
                    status=cleared_status,
                    provider=None,
                )
            )
        else:
            # Existing .loc.tsv translation or untranslated, with provider "manual" when text is present.
            provider = "manual" if row.translation_text else None
            overlaid.append(
                DriftRow(
                    source_filename=row.source_filename,
                    key=row.key,
                    parent_text=row.parent_text,
                    translation_text=row.translation_text,
                    status=row.status,
                    provider=provider,
                )
            )
    return overlaid


def _find_parent_preview_image(mod: WH3TranslationMod) -> Path | None:
    """Resolve a preview `.png` for the translation mod from its parent workshop folder.

    Each Workshop mod has a single preview `.png` in its content folder.
    The FIRST parent's preview is used so dashboard cards anchor to the translated game content.

    Args:
        mod: Translation mod whose parent folder(s) to scan.

    Returns:
        First `.png` in the first existing parent folder, or `None` if no folder is reachable or none has a `.png`.
    """
    for parent_id in mod.parent_workshop_ids:
        folder = tw3_workshop_content_dir(parent_id)
        if folder is None or not folder.exists():
            continue
        for png in sorted(folder.glob("*.png")):
            return png
    return None


def _preview_url_for(mod: WH3TranslationMod) -> str | None:
    """Build the preview-image route URL for a mod, or `None` when no preview file is found.

    Relative to `API_BASE` so the frontend can concatenate `${API_BASE}${url}` as it does for Chrono Ark previews.

    Args:
        mod: Translation mod to check.

    Returns:
        `/games/total_war_warhammer_3/translation/mods/{id}/preview`, or `None`.
    """
    if _find_parent_preview_image(mod) is None:
        return None
    return f"/games/total_war_warhammer_3/translation/mods/{mod.workshop_id}/preview"


def _has_unsynced_changes(mod_id: str, translation: dict[str, dict[str, LocRow]]) -> bool:
    """Return `True` when translations.json holds entries whose text differs from the user's `.loc.tsv`.

    A key whose text does not match, or has no `.loc.tsv` row, counts as unsynced.
    An empty-string override against non-empty `.loc.tsv` text is a pending clear and counts too.
    Mirrors Chrono Ark's `has_changes`.

    Args:
        mod_id: Workshop id of the translation mod.
        translation: Already-extracted map from `_extract_translation_strings(mod)`, passed in to avoid a second scan on the rescan hot path.

    Returns:
        `True` when any entry differs from the on-disk text.
    """
    raw = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
    if not raw:
        return False
    loc_by_key: dict[str, str] = {}
    for rows in translation.values():
        for key, row in rows.items():
            loc_by_key[key] = row.text
    for key, entry in raw.items():
        if not isinstance(entry, dict) or "text" not in entry:
            continue
        text = entry["text"] or ""
        # An empty override differing from non-empty .loc.tsv text is a pending clear.
        if (loc_by_key.get(key) or "") != text:
            return True
    return False


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Route models


class TranslationModSummary(BaseModel):
    """One translation-mod summary row."""

    workshop_id: str
    display_name: str
    parent_workshop_ids: list[str]
    local_source_dir: str
    source_language: str
    target_language: str
    # Relative URL to the parent mod's preview image, `None` when no preview file is reachable.
    preview_image_url: str | None = None


class RescanSummary(BaseModel):
    """Per-status row counts after a rescan."""

    mod_id: str
    counts: dict[str, int]
    # Zero-filled tally of the canonical six-state model, mirroring the per-row `canonical_status`.
    canonical_counts: dict[str, int]
    scanned_at: str
    # True when translations.json has entries whose text does not match the user's `.loc.tsv` files.
    has_unsynced_changes: bool = False
    # True when any of `source_game / character_name / background` is non-empty.
    has_mod_context: bool = False


class TranslationEdit(BaseModel):
    """Request body for `PUT /strings/{key}`."""

    text: str


class ModContext(BaseModel):
    """Body of `GET/PUT /mod-context`."""

    source_game: str = ""
    character_name: str = ""
    background: str = ""
    # Per-mod source language override, None falls back to the registry default.
    source_language_override: str | None = None
    # Per-mod target language override, None falls back to the registry default.
    target_language_override: str | None = None
    # When True, translated names not in the glossary are also sent with every prompt.
    include_translated_names: bool = False


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Routes


@router.get("/mods", response_model=list[TranslationModSummary])
def list_translation_mods() -> list[TranslationModSummary]:
    """Return the static registry of WH3 translation mods.

    Returns:
        One `TranslationModSummary` per registered mod.
    """
    return [
        TranslationModSummary(
            workshop_id=m.workshop_id,
            display_name=m.display_name,
            parent_workshop_ids=list(m.parent_workshop_ids),
            local_source_dir=str(m.local_source_dir),
            source_language=m.source_language,
            target_language=m.target_language,
            preview_image_url=_preview_url_for(m),
        )
        for m in WH3_TRANSLATION_MODS
    ]


@router.get("/mods/{mod_id}/preview")
def get_preview(mod_id: str) -> FileResponse:
    """Stream the parent mod's preview `.png` for the translation mod.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        `FileResponse` for the first `.png` in the first existing parent workshop folder.
    """
    mod = _require_mod(mod_id)
    png = _find_parent_preview_image(mod)
    if png is None:
        raise HTTPException(404, f"no preview image found for {mod_id}")
    return FileResponse(png, media_type="image/png")


@router.post("/mods/{mod_id}/rescan", response_model=RescanSummary)
def rescan(mod_id: str) -> RescanSummary:
    """Re-extract parent strings, re-read local translations and compute drift.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        `RescanSummary` with per-status counts, scan timestamp, `has_unsynced_changes` and `has_mod_context`.
    """
    mod = _require_mod(mod_id)
    parent = _extract_all_parent_strings(mod)
    translation = _extract_translation_strings(mod)
    snapshot = load_parent_snapshot(mod_id)

    drift = compute_drift(parent=parent, translation=translation, snapshot=snapshot)

    # Adds never-seen keys and backfills text on matching ones. Drifted keys keep their old entry so they stay changed.
    save_parent_snapshot(mod_id, refresh_unchanged(snapshot, parent))

    # Count from the overlaid rows, not raw drift, so empty-string clears and in-flight overrides match the strings view.
    raw_translations = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
    overlaid = _overlay_translations(drift, raw_translations)
    # Blank parent source has nothing to translate, so it is left out of the progress counts like Chrono Ark.
    counts: dict[str, int] = {"translated": 0, "untranslated": 0, "stale": 0, "orphan": 0}
    for row in overlaid:
        if row.parent_text is not None and not row.parent_text.strip():
            continue
        counts[row.status] += 1

    # Canonical six-state tally for the shared status pills, zero-filled so every state is present.
    # Orphan rows are excluded to match the strings table.
    canonical_counts: dict[str, int] = {"synced": 0, "untouched": 0, "pending": 0, "changed": 0, "missing": 0, "untranslatable": 0}
    for srow in to_status_rows([d for d in drift if d.status != "orphan"], raw_translations):
        canonical_counts[srow.status] += 1

    ctx = character_context.load_character_context(mod_id, game_id=GAME_ID)
    has_mod_context = bool((ctx.get("source_game") or "").strip() or (ctx.get("character_name") or "").strip() or (ctx.get("background") or "").strip())

    return RescanSummary(
        mod_id=mod_id,
        counts=counts,
        canonical_counts=canonical_counts,
        scanned_at=datetime.now(UTC).isoformat(),
        has_unsynced_changes=_has_unsynced_changes(mod_id, translation),
        has_mod_context=has_mod_context,
    )


def _drift_and_overlay(mod_id: str, mod: WH3TranslationMod) -> tuple[list[DriftRow], dict, list[DriftRow]]:
    """Compute a mod's drift rows and overlay `translations.json` onto them.

    Args:
        mod_id: Workshop id of the translation mod.
        mod: Registered translation mod.

    Returns:
        `(drift, raw_translations, overlaid)`, where `overlaid` has `translations.json` applied and orphan rows removed.
    """
    parent = _extract_all_parent_strings(mod)
    translation = _extract_translation_strings(mod)
    drift = compute_drift(parent=parent, translation=translation, snapshot=load_parent_snapshot(mod_id))
    raw_translations = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
    # Orphans (translated keys whose parent source is gone) are hidden from the table and pruned from disk on the next sync.
    overlaid = [r for r in _overlay_translations(drift, raw_translations) if r.status != "orphan"]
    return drift, raw_translations, overlaid


@router.get("/mods/{mod_id}/strings")
def get_strings(mod_id: str, status: Literal["translated", "untranslated", "stale", "orphan"] | None = None) -> list[dict]:
    """Return drift rows for a mod, optionally filtered by status.

    Overlays `translations.json` so in-flight edits (user PUTs, Claude batches) show immediately, taking `translation_text` and `provider` from it when present.
    Otherwise they come from the `.loc.tsv` with `provider` defaulting to `"manual"`.
    An empty-string override is an explicit clear, shown as empty and `untranslated`.

    Args:
        mod_id: Workshop id of the translation mod.
        status: Optional filter (`"translated"`, `"untranslated"`, `"stale"`, `"orphan"`).

    Returns:
        Serialized `DriftRow` dicts.
    """
    mod = _require_mod(mod_id)
    drift, raw_translations, overlaid = _drift_and_overlay(mod_id, mod)
    # Pre-overlay translation_text is the on-disk .loc.tsv value, i.e. the "previous" translation (like Chrono Ark's original_english).
    previous_by_key = {r.key: r.translation_text for r in drift}
    canonical = {(r.source_file, r.key): r.status for r in to_status_rows(drift, raw_translations)}

    if status:
        overlaid = [r for r in overlaid if r.status == status]

    return [{**_serialize_drift_row(r), "canonical_status": canonical.get((r.source_filename, r.key)), "previous_text": previous_by_key.get(r.key)} for r in overlaid]


def current_shipped_strings(mod_id: str) -> dict[str, dict[str, str]]:
    """Return what the next publish of a mod will ship, hashed for changenote diffing.

    Uses the same overlaid rows as `get_strings`, which are what Sync writes, so it is already right before the sync-first step runs.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        `{source_filename: {key: hash}}` from `workshop.change_notes.shipped_strings`.
    """
    mod = _require_mod(mod_id)
    _, _, overlaid = _drift_and_overlay(mod_id, mod)
    return tcn.shipped_strings(overlaid)


@router.put("/mods/{mod_id}/strings/{key}")
def put_string(mod_id: str, key: str, edit: TranslationEdit) -> dict:
    """Persist a translation edit.

    Args:
        mod_id: Workshop id of the translation mod.
        key: String key to save.
        edit: Body with the translated text.

    Returns:
        `{"status": "ok"}`.
    """
    mod = _require_mod(mod_id)
    raw = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
    now = datetime.now(UTC).isoformat()
    existing = raw.get(key, {})
    raw[key] = {
        "text": edit.text,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "provider": "manual",
    }
    translation_store.save_translations_raw(mod_id, raw, game_id=GAME_ID)
    # A manual edit settles a changed row, so accept the current source as its baseline. Best effort since extraction may need RPFM.
    try:
        save_parent_snapshot(mod_id, accept_keys(load_parent_snapshot(mod_id), _extract_all_parent_strings(mod), {key}))
    except Exception as e:
        logger.warning("Could not accept the current source for %s in mod %s: %s", key, mod_id, e)
    return {"status": "ok"}


@router.get("/mods/{mod_id}/mod-context")
def get_mod_context(mod_id: str) -> dict:
    """Return the mod context for a registered translation mod.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        Mod context fields (`source_game`, `character_name`, `background`), the per-mod language overrides, and `include_translated_names`.
    """
    _require_mod(mod_id)
    ctx = character_context.load_character_context(mod_id, game_id=GAME_ID)
    ctx["source_language_override"] = load_source_language_override(mod_id, game_id=GAME_ID)
    ctx["target_language_override"] = load_target_language_override(mod_id, game_id=GAME_ID)
    ctx["include_translated_names"] = mod_settings.load_include_translated_names(mod_id, game_id=GAME_ID)
    return ctx


@router.put("/mods/{mod_id}/mod-context")
def put_mod_context(mod_id: str, ctx: ModContext) -> dict:
    """Save mod context for a registered translation mod.

    Args:
        mod_id: Workshop id of the translation mod.
        ctx: Context fields plus optional language overrides.

    Returns:
        `{"status": "ok"}`.
    """
    _require_mod(mod_id)
    character_context.save_character_context(mod_id, ctx.model_dump(), game_id=GAME_ID)
    save_source_language_override(mod_id, ctx.source_language_override, game_id=GAME_ID)
    save_target_language_override(mod_id, ctx.target_language_override, game_id=GAME_ID)
    mod_settings.save_include_translated_names(mod_id, ctx.include_translated_names, game_id=GAME_ID)
    return {"status": "ok"}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Plan 3 routes


class SnapshotCreateRequest(BaseModel):
    """Request body for `POST /mods/{mod_id}/snapshots`."""

    label: str = "manual save"


class GlossaryEntry(BaseModel):
    """One glossary entry, keyed by `english` with `source` and `category` values."""

    english: str
    source: str = ""
    category: str = ""


class GlossaryApplyAllRequest(BaseModel):
    """Body for `POST /glossary/apply-all`."""

    old_english: str
    new_english: str


@router.post("/mods/{mod_id}/clear-translations")
def clear_translations(mod_id: str) -> dict:
    """Clear all English by writing empty-string overrides for every key that currently has text, after a pre-clear auto-snapshot.

    The empty overrides mask the `.loc.tsv` content so cleared rows show as untranslated.
    The files are untouched here and the blanks reach disk on the next Sync,
    as with AI/manual translations.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{"cleared": N}`, the number of keys overridden with an empty string.
    """
    mod = _require_mod(mod_id)
    _backup(mod, "pre-clear-translations")

    raw = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
    translation = _extract_translation_strings(mod)

    # Every key that currently shows English, from translations.json or the .loc.tsv files.
    keys_with_english: set[str] = set()
    for key, entry in raw.items():
        if isinstance(entry, dict) and entry.get("text"):
            keys_with_english.add(key)
    for rows in translation.values():
        for key, row in rows.items():
            if row.text:
                keys_with_english.add(key)

    # Empty-string overrides mask the .loc.tsv content so rows show as untranslated until synced.
    now = datetime.now(UTC).isoformat()
    cleared: dict[str, dict] = {}
    for key in keys_with_english:
        existing = raw.get(key)
        if not isinstance(existing, dict):
            existing = {}
        cleared[key] = {
            "text": "",
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "provider": existing.get("provider") or "manual",
        }
    translation_store.save_translations_raw(mod_id, cleared, game_id=GAME_ID)
    return {"cleared": len(cleared)}


@router.post("/mods/{mod_id}/sync")
def sync_changes(mod_id: str) -> dict:
    """Apply translations.json into the user's .loc.tsv files (surgical patch).

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{"per_file": {absolute_path: count}, "removed_orphans": N, "pack_built": bool, "pack_error": str | None}` for the writeback, orphan pruning and pack rebuild.
    """
    mod = _require_mod(mod_id)
    _backup(mod, "pre-sync")

    # Prune orphans (translated keys whose parent source is gone) from the .loc.tsv files and translations.json.
    # The pre-sync snapshot keeps them recoverable.
    parent = _extract_all_parent_strings(mod)
    translation = _extract_translation_strings(mod)
    snapshot = load_parent_snapshot(mod_id)
    orphans = [d for d in compute_drift(parent=parent, translation=translation, snapshot=snapshot) if d.status == "orphan"]
    removed_orphans = 0
    if orphans:
        keys_by_file: dict[str, set[str]] = {}
        for d in orphans:
            keys_by_file.setdefault(d.source_filename, set()).add(d.key)
        removed_orphans = sum(remove_keys_from_loc_tsv(mod, keys_by_file).values())
        orphan_keys = {d.key for d in orphans}
        raw = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)
        pruned = {k: v for k, v in raw.items() if k not in orphan_keys}
        if len(pruned) != len(raw):
            translation_store.save_translations_raw(mod_id, pruned, game_id=GAME_ID)

    drift = get_strings(mod_id)
    per_file = sync_translations_to_loc_tsv(mod, drift)

    # Drifted keys keep their old snapshot entry so they stay changed. Update Changed and Accept re-baseline those explicitly.
    save_parent_snapshot(mod_id, refresh_unchanged(load_parent_snapshot(mod_id), parent))

    # Rebuild the published .pack from the freshly written files.
    # Non-fatal since the writeback already succeeded, so problems are a warning. Skipped when nothing was written.
    pack_built = False
    pack_error: str | None = None
    if sum(per_file.values()) > 0:
        try:
            rpfm = resolve_rpfm_cli_path()
            if rpfm is None:
                raise RpfmNotConfiguredError("RPFM not configured; set SWMT_TW3_RPFM_CLI_PATH or place rpfm_cli.exe in SWMT_TW3_HELPER_PATH")
            content_dir = tw3_workshop_content_dir(mod_id)
            if content_dir is None:
                raise PackBuildError("TW3 Steam library drive is not configured")
            build_translation_pack(mod, rpfm_cli_path=rpfm, workshop_content_dir=content_dir)
            pack_built = True
        except PackBuildError as exc:
            pack_error = str(exc)

    return {"per_file": per_file, "removed_orphans": removed_orphans, "pack_built": pack_built, "pack_error": pack_error}


class AcceptChangedRequest(BaseModel):
    """Body of `POST /mods/{mod_id}/accept-changed`."""

    # Keys to accept. None accepts every currently changed key.
    keys: list[str] | None = None


@router.post("/mods/{mod_id}/accept-changed")
def accept_changed(mod_id: str, req: AcceptChangedRequest) -> dict:
    """Accept the current source text as the baseline for changed rows, keeping their translations.

    Args:
        mod_id: Workshop id of the translation mod.
        req: Keys to accept, or `None` for every changed row.

    Returns:
        `{"accepted": N}`, the rows re-baselined.
    """
    mod = _require_mod(mod_id)
    parent = _extract_all_parent_strings(mod)
    snapshot = load_parent_snapshot(mod_id)
    drift = compute_drift(parent=parent, translation=_extract_translation_strings(mod), snapshot=snapshot)
    changed = {r.key for r in drift if r.status == "stale"}
    keys = changed if req.keys is None else changed & set(req.keys)
    if keys:
        save_parent_snapshot(mod_id, accept_keys(snapshot, parent, keys))
    return {"accepted": len(keys)}


@router.get("/mods/{mod_id}/snapshots")
def get_snapshots(mod_id: str) -> list[dict]:
    """Return snapshot metadata for a mod, newest first.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Backup dicts with id, reason, kind, created_at and counts, empty when none exist.
    """
    _require_mod(mod_id)
    return history_manager.list_backups(mod_id, game_id=GAME_ID)


@router.post("/mods/{mod_id}/snapshots")
def post_snapshot(mod_id: str, req: SnapshotCreateRequest) -> dict:
    """Create a manual snapshot of the mod's full state.

    Args:
        mod_id: Workshop id of the WH3 mod.
        req: Body with the snapshot label.

    Returns:
        `{"status": "saved", "id": backup_id}`, or `{"status": "empty"}` when there was nothing to back up.
    """
    mod = _require_mod(mod_id)
    backup_id = _backup(mod, req.label, kind="manual")
    if backup_id is None:
        return {"status": "empty"}
    return {"status": "saved", "id": backup_id}


@router.post("/mods/{mod_id}/snapshots/{sid}/restore")
def post_restore_snapshot(mod_id: str, sid: str) -> dict:
    """Restore a mod's state from a snapshot, auto-creating a pre-restore snapshot first.

    Args:
        mod_id: Workshop id of the WH3 mod.
        sid: Id of the snapshot to restore.

    Returns:
        `{"status": "ok"}`.
    """
    mod = _require_mod(mod_id)
    if not history_manager.restore_backup(mod_id, sid, game_id=GAME_ID, extra_files=user_loc_tsv_files(mod)):
        raise HTTPException(404, f"snapshot {sid} not found")
    return {"status": "ok"}


@router.delete("/mods/{mod_id}/snapshots/{sid}")
def delete_snapshot_route(mod_id: str, sid: str) -> dict:
    """Delete one snapshot from a mod's history.

    Args:
        mod_id: Workshop id of the WH3 mod.
        sid: Id of the snapshot to delete.

    Returns:
        `{"status": "ok"}`.
    """
    _require_mod(mod_id)
    history_manager.delete_backup(mod_id, sid, game_id=GAME_ID)
    return {"status": "ok"}


@router.get("/glossary")
def get_base_glossary() -> dict:
    """Return the WH3 base-game terminology glossary.

    Returns:
        `{"terms": {...}}`, empty when not built yet.
    """
    return glossary_store.load_base_glossary()


@router.get("/mods/{mod_id}/glossary")
def get_glossary(mod_id: str) -> dict:
    """Return the per-mod glossary.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Glossary keyed by English term.
    """
    _require_mod(mod_id)
    return glossary_store.load_glossary(mod_id)


@router.post("/mods/{mod_id}/glossary")
def post_glossary_term(mod_id: str, entry: GlossaryEntry) -> dict:
    """Add or replace a glossary entry.

    Args:
        mod_id: Workshop id of the WH3 mod.
        entry: Entry with `english`, `source`, `category`.

    Returns:
        `{"status": "ok"}`.
    """
    _require_mod(mod_id)
    glossary_store.add_term(mod_id, entry.model_dump())
    return {"status": "ok"}


def _rename_in_translations(mod, mod_id: str, source: str | None, old_english: str, new_english: str) -> int:
    """Rename `old_english` to `new_english` in every translation whose source text contains `source`.

    Rows come from the translation pack with translations.json overlaid, so pack-only translations are renamed too. Changed rows are saved to
    translations.json and show as pending until the next Sync.

    Args:
        mod: Resolved `WH3TranslationMod`.
        mod_id: Workshop id of the WH3 mod.
        source: Term's source text, where empty renames nothing and `None` renames every translation.
        old_english: English to replace, matched as a whole term.
        new_english: Replacement English.

    Returns:
        Number of translations changed.
    """
    if source == "" or old_english == new_english:
        return 0
    parent = _extract_all_parent_strings(mod)
    drift = compute_drift(parent=parent, translation=_extract_translation_strings(mod), snapshot=load_parent_snapshot(mod_id))
    raw = translation_store.load_translations_raw(mod_id, game_id=GAME_ID)

    rows = list(_overlay_translations(drift, raw))
    changes = rename_term(((row.key, row.parent_text or "", row.translation_text or "") for row in rows), old_english, new_english, source)
    now = datetime.now(UTC).isoformat()
    for row in rows:
        if row.key not in changes:
            continue
        existing = raw.get(row.key)
        if not isinstance(existing, dict):
            existing = {}
        raw[row.key] = {"text": changes[row.key], "created_at": existing.get("created_at") or now, "updated_at": now, "provider": existing.get("provider") or row.provider or "manual"}
    if changes:
        translation_store.save_translations_raw(mod_id, raw, game_id=GAME_ID)
    return len(changes)


@router.put("/mods/{mod_id}/glossary/{english}")
def put_glossary_term(mod_id: str, english: str, entry: GlossaryEntry) -> dict:
    """Update (and optionally rename) a glossary entry.

    A new English also replaces the old English in every translation whose source contains the term's old source, after a restorable snapshot.

    Args:
        mod_id: Workshop id of the WH3 mod.
        english: Existing English term key to update.
        entry: New `{english, source, category}`, where a different `english` renames the entry.

    Returns:
        `{"status": "ok", "replaced": N}`, where N counts translations the rename changed.
    """
    mod = _require_mod(mod_id)
    old_source = (glossary_store.load_glossary(mod_id).get(english) or {}).get("source", "")
    renaming = bool(old_source) and entry.english != english
    if renaming:
        _backup(mod, f"Before renaming glossary term {english}")
    glossary_store.update_term(mod_id, english, entry.model_dump())
    replaced = _rename_in_translations(mod, mod_id, old_source, english, entry.english) if renaming else 0
    return {"status": "ok", "replaced": replaced}


@router.delete("/mods/{mod_id}/glossary")
def delete_all_glossary_terms(mod_id: str) -> dict:
    """Remove every term from a mod's glossary, taking a restorable snapshot first if there is anything to delete.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{"status": "success", "deleted": N}`.
    """
    mod = _require_mod(mod_id)
    if glossary_store.load_glossary(mod_id):
        _backup(mod, "Before deleting all glossary terms")
    deleted = glossary_store.delete_all_terms(mod_id)
    return {"status": "success", "deleted": deleted}


@router.delete("/mods/{mod_id}/glossary/{english}")
def delete_glossary_term(mod_id: str, english: str) -> dict:
    """Delete a glossary entry by English term.

    Args:
        mod_id: Workshop id of the WH3 mod.
        english: English term key to delete.

    Returns:
        `{"status": "ok"}`.
    """
    _require_mod(mod_id)
    glossary_store.delete_term(mod_id, english)
    return {"status": "ok"}


@router.post("/mods/{mod_id}/glossary/apply-all")
def post_glossary_apply_all(mod_id: str, req: GlossaryApplyAllRequest) -> dict:
    """Rename `old_english` to `new_english` as a whole term in every translation, after a restorable snapshot.

    Args:
        mod_id: Workshop id of the WH3 mod.
        req: Body with `old_english` and `new_english`.

    Returns:
        `{"replaced": N}`, where N counts changed translations.
    """
    mod = _require_mod(mod_id)
    _backup(mod, f"pre-apply-all rename {req.old_english}")
    return {"replaced": _rename_in_translations(mod, mod_id, None, req.old_english, req.new_english)}


@router.get("/mods/{mod_id}/api-responses")
def get_api_responses(mod_id: str) -> list[dict]:
    """List a mod's API response entries, newest first.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Audit entries, empty if no log exists.
    """
    _require_mod(mod_id)
    return api_response_log.list_entries(mod_id, game_id=GAME_ID)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Mod folder open helper


@router.post("/mods/{mod_id}/open-folder")
def open_mod_folder(mod_id: str) -> dict:
    """Open the mod's local source directory in the OS file explorer.

    Args:
        mod_id: Workshop id of the translation mod.

    Returns:
        `{"status": "ok"}`.
    """
    mod = _require_mod(mod_id)
    folder = mod.local_source_dir
    if not folder.exists():
        raise HTTPException(404, f"local source dir not found: {folder}")
    open_path(folder)
    return {"status": "ok"}


@router.post("/mods/{mod_id}/open-source-file/{filename}")
def open_source_file(mod_id: str, filename: str) -> dict:
    """Open one of the mod's source `.loc.tsv` files in the OS default application.

    Resolves the normalized parent filename to the user's on-disk file, which may carry the mod prefix.

    Args:
        mod_id: Workshop id of the translation mod.
        filename: Normalized `.loc.tsv` filename from the Source column (e.g. `"units.loc.tsv"`).

    Returns:
        `{"status": "ok", "path": <resolved path>}`.
    """
    mod = _require_mod(mod_id)
    target = _find_existing_user_file(mod, filename)
    if target is None or not target.is_file():
        raise HTTPException(404, f"source file not found: {filename}")
    open_path(target)
    return {"status": "ok", "path": str(target)}
