"""One-time migration: move legacy flat storage (mods, glossary, translation memory) into `games/chrono_ark/`. Idempotent via a marker file."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.core.settings import settings

LOG = logging.getLogger(__name__)

_GAME_ID = "chrono_ark"
_MARKER_RELATIVE = Path("_migrations") / "v1_complete.marker"
_LEGACY_TO_NEW = [
    ("mods", "mods"),
    ("glossary.json", "glossary.json"),
    ("translation_memory.json", "translation_memory.json"),
]


def _root() -> Path:
    """Return the configured storage root."""
    return Path(settings.storage_path)


def _marker_path() -> Path:
    """Return the migration completion marker path."""
    return _root() / _MARKER_RELATIVE


def run_migration() -> bool:
    """Move legacy storage into the per-game namespace if not already done.

    Returns:
        Whether the migration ran.
    """
    marker = _marker_path()
    if marker.exists():
        LOG.info("Storage migration v1->v2 already complete; skipping.")
        return False

    root = _root()
    new_root = root / "games" / _GAME_ID
    new_root.mkdir(parents=True, exist_ok=True)

    for legacy_name, new_name in _LEGACY_TO_NEW:
        legacy = root / legacy_name
        target = new_root / new_name
        if legacy.exists() and not target.exists():
            LOG.info("Migrating %s -> %s", legacy, target)
            shutil.move(str(legacy), str(target))

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("v1->v2 migration complete\n", encoding="utf-8")
    LOG.info("Storage migration v1->v2 complete; marker written at %s", marker)
    return True
