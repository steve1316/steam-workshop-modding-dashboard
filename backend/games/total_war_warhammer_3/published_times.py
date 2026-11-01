"""When this app last published each Workshop item. Steam's local manifest lags a fresh upload, so the card prefers this."""

from __future__ import annotations

import json
import time
from pathlib import Path

from backend.core.json_store import write_json
from backend.games.storage_paths import game_storage_path

GAME_ID = "total_war_warhammer_3"
FILENAME = "published_times.json"


def _path() -> Path:
    """Return the published times file path.

    Returns:
        `<root>/published_times.json`.
    """
    return game_storage_path(GAME_ID) / FILENAME


def _load() -> dict[str, float]:
    """Read the stored times.

    Returns:
        `{workshop_id: unix_seconds}`, empty when missing or unreadable.
    """
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))} if isinstance(data, dict) else {}


def record(workshop_id: str, when: float | None = None) -> None:
    """Store the time of a successful publish.

    Args:
        workshop_id: Published Workshop id.
        when: Publish time in unix seconds, defaults to now.
    """
    times = _load()
    times[workshop_id] = time.time() if when is None else when
    write_json(_path(), times)


def get(workshop_id: str) -> float | None:
    """Look up the stored publish time.

    Args:
        workshop_id: Workshop id to look up.

    Returns:
        Unix seconds, or None when this app has not published the item.
    """
    return _load().get(workshop_id)
