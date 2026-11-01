"""Per-game storage path resolution under `<STORAGE_PATH>/games/<game_id>`.

Legacy flat storage is migrated into this layout by `backend.scripts.migrate_storage_v1_to_v2` at startup.
"""

from __future__ import annotations

from pathlib import Path

from backend import config


def game_storage_path(game_id: str) -> Path:
    """Return the per-game storage directory for `game_id`.

    Args:
        game_id: Adapter id (e.g. `"chrono_ark"`).

    Returns:
        `<STORAGE_PATH>/games/<game_id>`.
    """
    if not game_id:
        raise ValueError("game_id must not be empty")
    return Path(config.STORAGE_PATH) / "games" / game_id


def mods_path(game_id: str) -> Path:
    """Return `<game_storage_path>/mods` for `game_id`."""
    return game_storage_path(game_id) / "mods"


def glossary_path(game_id: str) -> Path:
    """Return `<game_storage_path>/glossary.json` for `game_id`."""
    return game_storage_path(game_id) / "glossary.json"


def translation_memory_path(game_id: str) -> Path:
    """Return `<game_storage_path>/translation_memory.json` for `game_id`."""
    return game_storage_path(game_id) / "translation_memory.json"
