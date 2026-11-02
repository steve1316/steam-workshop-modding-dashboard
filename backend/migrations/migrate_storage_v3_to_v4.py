"""One-time migration: fold Chrono Ark `translation_providers.json` into `translations.json` and drop the old `last_api_responses.json`.

Idempotent via a marker file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.settings import settings

LOG = logging.getLogger(__name__)

_GAME_ID = "chrono_ark"
_MARKER_RELATIVE = Path("_migrations") / "v3_to_v4_complete.marker"


def _root() -> Path:
    """Return the configured storage root."""
    return Path(settings.storage_path)


def _marker_path() -> Path:
    """Return the migration completion marker path."""
    return _root() / _MARKER_RELATIVE


def _read_json(path: Path) -> dict:
    """Read a JSON object, or an empty dict when missing or unreadable."""
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _fold_providers(mod_dir: Path) -> None:
    """Copy each key's provider from `translation_providers.json` onto its `translations.json` entry, then delete the provider file.

    Args:
        mod_dir: One Chrono Ark mod's storage dir.
    """
    providers_path = mod_dir / "translation_providers.json"
    if not providers_path.exists():
        return
    translations_path = mod_dir / "translations.json"
    translations = _read_json(translations_path)
    changed = False
    for key, provider in _read_json(providers_path).items():
        entry = translations.get(key)
        if isinstance(entry, str):
            entry = translations[key] = {"text": entry, "created_at": None, "updated_at": None}
        if isinstance(entry, dict) and provider:
            entry["provider"] = provider
            changed = True
    if changed:
        write_json(translations_path, translations)
    providers_path.unlink()


def run_migration() -> bool:
    """Fold the Chrono Ark provider files into translations.json if not already done.

    Returns:
        Whether the migration ran.
    """
    marker = _marker_path()
    if marker.exists():
        LOG.info("Storage migration v3->v4 already complete; skipping.")
        return False

    mods_dir = _root() / "games" / _GAME_ID / "mods"
    if mods_dir.is_dir():
        for mod_dir in mods_dir.iterdir():
            if not mod_dir.is_dir():
                continue
            _fold_providers(mod_dir)
            (mod_dir / "last_api_responses.json").unlink(missing_ok=True)

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("v3->v4 migration complete\n", encoding="utf-8")
    LOG.info("Storage migration v3->v4 complete; marker written at %s", marker)
    return True
