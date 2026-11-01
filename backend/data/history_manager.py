"""Timestamped per-mod backups taken before destructive operations, so the user can restore earlier states."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path, safe_child


def _history_dir(mod_id: str, *, game_id: str) -> Path:
    """Return the history directory for a mod, which may not exist yet.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        The mod's `history/` directory.
    """
    mods_dir = mods_path(game_id)
    return mods_dir / mod_id / "history"


def create_backup(mod_id: str, reason: str, *, game_id: str, kind: str = "auto") -> str | None:
    """Create a timestamped backup of the mod's current state.

    Args:
        mod_id: Mod's Workshop id.
        reason: Why the backup was created, e.g. "Before clearing translations".
        game_id: Game the mod belongs to.
        kind: "auto" before destructive ops, "manual" for user-requested snapshots.

    Returns:
        The backup id (its folder name), or None if there was nothing to back up.
    """
    mods_dir = mods_path(game_id)
    mod_dir = mods_dir / mod_id

    files_to_backup = [
        "translations.json",
        "glossary.json",
        "pending_suggestions.json",
        "progress.json",
        "synced_keys.json",
        "last_csv_hash.json",
        "pre_export_english.json",
        "character_context.json",
        "mod_settings.json",
    ]
    if not any((mod_dir / f).exists() for f in files_to_backup):
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    hist_dir = _history_dir(mod_id, game_id=game_id)
    hist_dir.mkdir(parents=True, exist_ok=True)
    # A second backup within the same second, e.g. "Before restore", must not overwrite the first. The suffix still sorts newest first.
    backup_dir = hist_dir / timestamp
    suffix = 2
    while backup_dir.exists():
        backup_dir = hist_dir / f"{timestamp}_{suffix}"
        suffix += 1
    backup_dir.mkdir()

    backed_up = False
    for filename in files_to_backup:
        src = mod_dir / filename
        if src.exists():
            shutil.copy2(src, backup_dir / filename)
            backed_up = True

    if not backed_up:
        shutil.rmtree(backup_dir)
        return None

    translated_count = 0
    total_count = 0
    glossary_count = 0
    progress_path = mod_dir / "progress.json"
    if progress_path.exists():
        with open(progress_path, encoding="utf-8") as pf:
            progress = json.load(pf)
            total_count = progress.get("total_keys", 0)
            translated_count = len(progress.get("translated", []))
    glossary_path = mod_dir / "glossary.json"
    if glossary_path.exists():
        with open(glossary_path, encoding="utf-8") as gf:
            glossary = json.load(gf)
            glossary_count = len(glossary.get("terms", {}))

    meta = {
        "timestamp": timestamp,
        "reason": reason,
        "kind": kind,
        "created_at": datetime.now(UTC).isoformat(),
        "files": [f for f in files_to_backup if (mod_dir / f).exists()],
        "translated_count": translated_count,
        "total_count": total_count,
        "glossary_count": glossary_count,
    }
    write_json(backup_dir / "meta.json", meta)

    _prune_backups(mod_id, max_backups=20, game_id=game_id)

    return backup_dir.name


def list_backups(mod_id: str, *, game_id: str) -> list[dict]:
    """List all available backups for a mod, newest first.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Backup metadata dicts with id, reason, created_at and files.
    """
    hist_dir = _history_dir(mod_id, game_id=game_id)
    if not hist_dir.is_dir():
        return []
    backups = []
    for entry in sorted(hist_dir.iterdir(), reverse=True):
        if entry.is_dir():
            meta_path = entry / "meta.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                meta["id"] = entry.name
                # Backfill the kind for older backups taken before the field existed.
                meta.setdefault("kind", "auto")
                # Backfill counts for older backups.
                if "translated_count" not in meta:
                    meta["translated_count"] = 0
                    meta["total_count"] = 0
                    meta["glossary_count"] = 0
                    progress_path = entry / "progress.json"
                    if progress_path.exists():
                        with open(progress_path, encoding="utf-8") as pf:
                            progress = json.load(pf)
                            meta["total_count"] = progress.get("total_keys", 0)
                            meta["translated_count"] = len(progress.get("translated", []))
                    glossary_path = entry / "glossary.json"
                    if glossary_path.exists():
                        with open(glossary_path, encoding="utf-8") as gf:
                            glossary = json.load(gf)
                            meta["glossary_count"] = len(glossary.get("terms", {}))
                backups.append(meta)
    return backups


def restore_backup(mod_id: str, backup_id: str, *, game_id: str) -> bool:
    """Restore a mod's state from a backup.

    Backs up the current state first, then copies the backed-up files into the mod directory.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Id of the backup to restore.
        game_id: Game the mod belongs to.

    Returns:
        False if the backup was not found.
    """
    mods_dir = mods_path(game_id)
    try:
        backup_dir = safe_child(_history_dir(mod_id, game_id=game_id), backup_id)
    except ValueError:
        return False

    if not backup_dir.exists():
        return False

    create_backup(mod_id, f"Before restore to {backup_id}", game_id=game_id)

    mod_dir = mods_dir / mod_id
    meta_path = backup_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        backed_up_files = set(meta.get("files", []))
        for filename in backed_up_files:
            src = backup_dir / filename
            if src.exists():
                shutil.copy2(src, mod_dir / filename)

        # The export targets (injector JSONs or mod CSVs) won't match the restored state, so strings must show PENDING, not SYNCED.
        for sync_file in ("synced_keys.json", "last_csv_hash.json", "pre_export_english.json", "last_export.json"):
            target = mod_dir / sync_file
            if target.exists():
                target.unlink()

    return True


def delete_backup(mod_id: str, backup_id: str, *, game_id: str) -> bool:
    """Delete a specific backup.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Id of the backup to delete.
        game_id: Game the mod belongs to.

    Returns:
        False if the backup was not found.
    """
    try:
        backup_dir = safe_child(_history_dir(mod_id, game_id=game_id), backup_id)
    except ValueError:
        return False
    if not backup_dir.exists():
        return False
    shutil.rmtree(backup_dir)
    return True


def _prune_backups(mod_id: str, max_backups: int = 20, *, game_id: str) -> None:
    """Remove oldest backups when the total exceeds `max_backups`.

    Args:
        mod_id: Mod's Workshop id.
        max_backups: Most backups to keep.
        game_id: Game the mod belongs to.
    """
    hist_dir = _history_dir(mod_id, game_id=game_id)
    entries = sorted([e for e in hist_dir.iterdir() if e.is_dir()], reverse=True)
    for old_entry in entries[max_backups:]:
        shutil.rmtree(old_entry)
