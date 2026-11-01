"""
Manages history backups for mod translation data.

Creates timestamped snapshots before destructive operations so the user
can restore previous states. Each backup captures translations.json,
glossary.json, pending_suggestions.json, and sync state files.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend.core.paths import safe_child
from backend.games.storage_paths import mods_path


def _history_dir(mod_id: str, storage_path: Optional[Path] = None) -> Path:
    """Return the history directory for a mod, creating it if needed.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        Path to the mod's `history/` directory.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "history"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(mod_id: str, reason: str, storage_path: Optional[Path] = None, kind: str = "auto") -> Optional[str]:
    """Create a timestamped backup of the mod's current state.

    Args:
        mod_id: The mod's Workshop ID.
        reason: Human-readable description of why the backup was created
            (e.g. "Before clearing translations", "Before translation run").
        storage_path: Base storage path override.
        kind: "auto" for backups taken automatically before destructive ops, "manual" for user-requested save snapshots.

    Returns:
        The backup ID (timestamp string), or None if there was nothing to back up.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    mod_dir = mods_dir / mod_id

    # Only back up if there's meaningful data.
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

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = _history_dir(mod_id, storage_path) / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copy files that exist.
    backed_up = False
    for filename in files_to_backup:
        src = mod_dir / filename
        if src.exists():
            shutil.copy2(src, backup_dir / filename)
            backed_up = True

    if not backed_up:
        shutil.rmtree(backup_dir)
        return None

    # Collect translation and glossary counts for the snapshot.
    translated_count = 0
    total_count = 0
    glossary_count = 0
    progress_path = mod_dir / "progress.json"
    if progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as pf:
            progress = json.load(pf)
            total_count = progress.get("total_keys", 0)
            translated_count = len(progress.get("translated", []))
    glossary_path = mod_dir / "glossary.json"
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as gf:
            glossary = json.load(gf)
            glossary_count = len(glossary.get("terms", {}))

    # Save metadata
    meta = {
        "timestamp": timestamp,
        "reason": reason,
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [f for f in files_to_backup if (mod_dir / f).exists()],
        "translated_count": translated_count,
        "total_count": total_count,
        "glossary_count": glossary_count,
    }
    with open(backup_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Prune old backups (keep last 20)
    _prune_backups(mod_id, max_backups=20, storage_path=storage_path)

    return timestamp


def list_backups(mod_id: str, storage_path: Optional[Path] = None) -> list[dict]:
    """List all available backups for a mod, newest first.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override.

    Returns:
        List of backup metadata dicts with id, reason, created_at, and files.
    """
    hist_dir = _history_dir(mod_id, storage_path)
    backups = []
    for entry in sorted(hist_dir.iterdir(), reverse=True):
        if entry.is_dir():
            meta_path = entry / "meta.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["id"] = entry.name
                # Backfill the kind for older backups taken before the field existed.
                meta.setdefault("kind", "auto")
                # Backfill counts for older backups that lack them.
                if "translated_count" not in meta:
                    meta["translated_count"] = 0
                    meta["total_count"] = 0
                    meta["glossary_count"] = 0
                    progress_path = entry / "progress.json"
                    if progress_path.exists():
                        with open(progress_path, "r", encoding="utf-8") as pf:
                            progress = json.load(pf)
                            meta["total_count"] = progress.get("total_keys", 0)
                            meta["translated_count"] = len(progress.get("translated", []))
                    glossary_path = entry / "glossary.json"
                    if glossary_path.exists():
                        with open(glossary_path, "r", encoding="utf-8") as gf:
                            glossary = json.load(gf)
                            meta["glossary_count"] = len(glossary.get("terms", {}))
                backups.append(meta)
    return backups


def restore_backup(mod_id: str, backup_id: str, storage_path: Optional[Path] = None) -> bool:
    """Restore a mod's state from a backup.

    Creates a backup of the current state first (reason: "Before restore"),
    then copies all backed-up files into the mod directory.

    Args:
        mod_id: The mod's Workshop ID.
        backup_id: The timestamp ID of the backup to restore.
        storage_path: Base storage path override.

    Returns:
        True if the restore was successful, False if the backup was not found.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    try:
        backup_dir = safe_child(_history_dir(mod_id, storage_path), backup_id)
    except ValueError:
        return False

    if not backup_dir.exists():
        return False

    # Create a backup of current state before restoring
    create_backup(mod_id, f"Before restore to {backup_id}", storage_path)

    mod_dir = mods_dir / mod_id
    meta_path = backup_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        backed_up_files = set(meta.get("files", []))
        for filename in backed_up_files:
            src = backup_dir / filename
            if src.exists():
                shutil.copy2(src, mod_dir / filename)

        # Always remove sync state files after restore. The export
        # targets (injector JSONs or mod CSVs) won't match the restored
        # state, so strings should appear as PENDING, not SYNCED.
        for sync_file in ("synced_keys.json", "last_csv_hash.json", "pre_export_english.json", "last_export.json"):
            target = mod_dir / sync_file
            if target.exists():
                target.unlink()

    return True


def delete_backup(mod_id: str, backup_id: str, storage_path: Optional[Path] = None) -> bool:
    """Delete a specific backup.

    Args:
        mod_id: The mod's Workshop ID.
        backup_id: The timestamp ID of the backup to delete.
        storage_path: Base storage path override.

    Returns:
        True if the backup was deleted, False if it was not found.
    """
    try:
        backup_dir = safe_child(_history_dir(mod_id, storage_path), backup_id)
    except ValueError:
        return False
    if not backup_dir.exists():
        return False
    shutil.rmtree(backup_dir)
    return True


def _prune_backups(mod_id: str, max_backups: int = 20, storage_path: Optional[Path] = None) -> None:
    """Remove oldest backups when the total exceeds `max_backups`.

    Args:
        mod_id: The mod's Workshop ID.
        max_backups: Maximum number of backups to retain.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    hist_dir = _history_dir(mod_id, storage_path)
    entries = sorted([e for e in hist_dir.iterdir() if e.is_dir()], reverse=True)
    for old_entry in entries[max_backups:]:
        shutil.rmtree(old_entry)
