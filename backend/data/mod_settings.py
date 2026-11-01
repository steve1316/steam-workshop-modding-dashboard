"""Load and save per-mod settings such as source and target language overrides."""

import json
from datetime import datetime, timezone
from pathlib import Path
from backend.games.storage_paths import mods_path
from backend.core.json_store import write_json


def load_source_language_override(mod_id: str, *, storage_path: Path | None = None) -> str | None:
    """Return the source language override for a mod, or None for auto-detect.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        The override language name (e.g. `"Korean"`), or None if not set.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "mod_settings.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("source_language_override") or None
    except (json.JSONDecodeError, OSError):
        return None


def save_source_language_override(
    mod_id: str,
    language: str | None,
    *,
    storage_path: Path | None = None,
) -> None:
    """Save the source language override for a mod.

    Args:
        mod_id: The mod's Workshop ID.
        language: Language name to use as override, or None for auto-detect.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / "mod_settings.json"

    # Preserve any existing settings in the file.
    existing: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    existing["source_language_override"] = language if language else None
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    write_json(path, existing)


def load_target_language_override(mod_id: str, *, storage_path: Path | None = None) -> str | None:
    """Return the target language override for a mod, or None for default (English).

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.

    Returns:
        The override language name (e.g. `"Chinese"`), or None if not set.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "mod_settings.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("target_language_override") or None
    except (json.JSONDecodeError, OSError):
        return None


def save_target_language_override(
    mod_id: str,
    language: str | None,
    *,
    storage_path: Path | None = None,
) -> None:
    """Save the target language override for a mod.

    Args:
        mod_id: The mod's Workshop ID.
        language: Language name to use as target, or None for default (English).
        storage_path: Base storage path override. Defaults to `config.STORAGE_PATH`.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / "mod_settings.json"

    existing: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    existing["target_language_override"] = language if language else None
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    write_json(path, existing)
