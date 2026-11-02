"""Timestamped per-mod backups taken before destructive operations, so the user can restore earlier states.

Every game uses this store. A game's `HistoryProfile` says which mod-dir files a backup copies.
"""

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path, safe_child

MAX_BACKUPS = 20


@dataclass(frozen=True)
class HistoryProfile:
    """What a game's backups capture.

    Attributes:
        files: Mod-dir files copied into each backup.
        reset_on_restore: Sync-state files deleted after a restore because the exported output no longer matches the restored state.
    """

    files: tuple[str, ...]
    reset_on_restore: tuple[str, ...] = ()


_CHRONO_ARK = HistoryProfile(
    files=(
        "translations.json",
        "glossary.json",
        "pending_suggestions.json",
        "progress.json",
        "synced_keys.json",
        "last_csv_hash.json",
        "pre_export_english.json",
        "character_context.json",
        "mod_settings.json",
    ),
    reset_on_restore=("synced_keys.json", "last_csv_hash.json", "pre_export_english.json", "last_export.json"),
)

_PROFILES = {
    "chrono_ark": _CHRONO_ARK,
    "total_war_warhammer_3": HistoryProfile(files=("translations.json", "parent_snapshot.json", "api_responses.json", "glossary.json")),
}


def history_dir(mod_id: str, *, game_id: str) -> Path:
    """Return the history directory for a mod, which may not exist yet.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        The mod's `history/` directory.
    """
    return mods_path(game_id) / mod_id / "history"


def new_backup_dir(hist_dir: Path, timestamp: str) -> Path:
    """Create an empty backup folder named after `timestamp`.

    A second backup within the same second, e.g. "Before restore", must not overwrite the first. The suffix still sorts newest first.

    Args:
        hist_dir: The mod's history directory.
        timestamp: `%Y%m%d_%H%M%S` creation time.

    Returns:
        The new folder.
    """
    hist_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = hist_dir / timestamp
    suffix = 2
    while backup_dir.exists():
        backup_dir = hist_dir / f"{timestamp}_{suffix}"
        suffix += 1
    backup_dir.mkdir()
    return backup_dir


def _counts(folder: Path) -> dict[str, int]:
    """Read the translated, total and glossary counts from the progress and glossary files in `folder`.

    Args:
        folder: A mod dir or a backup folder.

    Returns:
        `translated_count`, `total_count` and `glossary_count`.
    """
    counts = {"translated_count": 0, "total_count": 0, "glossary_count": 0}
    progress_path = folder / "progress.json"
    if progress_path.exists():
        with open(progress_path, encoding="utf-8") as pf:
            progress = json.load(pf)
            counts["total_count"] = progress.get("total_keys", 0)
            counts["translated_count"] = len(progress.get("translated", []))
    glossary_path = folder / "glossary.json"
    if glossary_path.exists():
        with open(glossary_path, encoding="utf-8") as gf:
            counts["glossary_count"] = len(json.load(gf).get("terms", {}))
    return counts


def create_backup(mod_id: str, reason: str, *, game_id: str, kind: str = "auto", extra_files: Iterable[Path] = ()) -> str | None:
    """Create a timestamped backup of the mod's current state.

    Args:
        mod_id: Mod's Workshop id.
        reason: Why the backup was created, e.g. "Before clearing translations".
        game_id: Game the mod belongs to.
        kind: "auto" before destructive ops, "manual" for user-requested snapshots.
        extra_files: Files outside the mod dir to capture too, restored to the same absolute paths.

    Returns:
        The backup id (its folder name), or None if there was nothing to back up.
    """
    mod_dir = mods_path(game_id) / mod_id
    files = [f for f in _PROFILES.get(game_id, _CHRONO_ARK).files if (mod_dir / f).exists()]
    extras = [p for p in extra_files if p.is_file()]
    if not files and not extras:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = new_backup_dir(history_dir(mod_id, game_id=game_id), timestamp)
    for filename in files:
        shutil.copy2(mod_dir / filename, backup_dir / filename)

    external: dict[str, str] = {}
    if extras:
        (backup_dir / "external").mkdir()
        for i, src in enumerate(extras):
            # Indexed names keep two same-named files from different folders apart.
            stored = f"external/{i}_{src.name}"
            shutil.copy2(src, backup_dir / stored)
            external[stored] = str(src)

    meta = {
        "timestamp": timestamp,
        "reason": reason,
        "kind": kind,
        "created_at": datetime.now(UTC).isoformat(),
        "files": files,
        "external": external,
        **_counts(mod_dir),
    }
    write_json(backup_dir / "meta.json", meta)

    _prune_backups(mod_id, max_backups=MAX_BACKUPS, game_id=game_id)

    return backup_dir.name


def list_backups(mod_id: str, *, game_id: str) -> list[dict]:
    """List all available backups for a mod, newest first.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Backup metadata dicts with id, reason, kind, created_at, files and counts.
    """
    hist_dir = history_dir(mod_id, game_id=game_id)
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
                # Backfill fields for older backups taken before they existed.
                meta.setdefault("kind", "auto")
                if "translated_count" not in meta:
                    meta.update(_counts(entry))
                backups.append(meta)
    return backups


def restore_backup(mod_id: str, backup_id: str, *, game_id: str, extra_files: Iterable[Path] = ()) -> bool:
    """Restore a mod's state from a backup.

    Backs up the current state first, then copies the backed-up files back into place.

    Args:
        mod_id: Mod's Workshop id.
        backup_id: Id of the backup to restore.
        game_id: Game the mod belongs to.
        extra_files: Files outside the mod dir to include in the pre-restore backup.

    Returns:
        False if the backup was not found.
    """
    try:
        backup_dir = safe_child(history_dir(mod_id, game_id=game_id), backup_id)
    except ValueError:
        return False

    if not backup_dir.is_dir():
        return False

    create_backup(mod_id, f"Before restore to {backup_id}", game_id=game_id, extra_files=extra_files)

    mod_dir = mods_path(game_id) / mod_id
    meta_path = backup_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        for filename in set(meta.get("files", [])):
            src = backup_dir / filename
            if src.exists():
                shutil.copy2(src, mod_dir / filename)
        for stored, original in meta.get("external", {}).items():
            src = backup_dir / stored
            if src.exists():
                Path(original).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, original)

        for sync_file in _PROFILES.get(game_id, _CHRONO_ARK).reset_on_restore:
            (mod_dir / sync_file).unlink(missing_ok=True)

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
        backup_dir = safe_child(history_dir(mod_id, game_id=game_id), backup_id)
    except ValueError:
        return False
    if not backup_dir.is_dir():
        return False
    shutil.rmtree(backup_dir)
    return True


def _prune_backups(mod_id: str, max_backups: int = MAX_BACKUPS, *, game_id: str) -> None:
    """Remove oldest backups when the total exceeds `max_backups`.

    Args:
        mod_id: Mod's Workshop id.
        max_backups: Most backups to keep.
        game_id: Game the mod belongs to.
    """
    hist_dir = history_dir(mod_id, game_id=game_id)
    entries = sorted([e for e in hist_dir.iterdir() if e.is_dir()], reverse=True)
    for old_entry in entries[max_backups:]:
        shutil.rmtree(old_entry)
