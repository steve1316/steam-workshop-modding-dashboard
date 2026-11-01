"""Load and save per-mod settings such as source and target language overrides."""

import json
from datetime import UTC, datetime

from backend.core.json_store import write_json
from backend.core.paths import mods_path


def load_source_language_override(mod_id: str, *, game_id: str) -> str | None:
    """Return the source language override for a mod, or None for auto-detect.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Language name, e.g. `"Korean"`.
    """
    mods_dir = mods_path(game_id)
    path = mods_dir / mod_id / "mod_settings.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("source_language_override") or None
    except (json.JSONDecodeError, OSError):
        return None


def save_source_language_override(
    mod_id: str,
    language: str | None,
    *,
    game_id: str,
) -> None:
    """Save the source language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        language: Language name, or None for auto-detect.
        game_id: Game the mod belongs to.
    """
    mods_dir = mods_path(game_id)
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / "mod_settings.json"

    # Keep the other settings already in the file.
    existing: dict = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    existing["source_language_override"] = language if language else None
    existing["updated_at"] = datetime.now(UTC).isoformat()

    write_json(path, existing)


def load_target_language_override(mod_id: str, *, game_id: str) -> str | None:
    """Return the target language override for a mod, or None for default (English).

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Language name, e.g. `"Chinese"`.
    """
    mods_dir = mods_path(game_id)
    path = mods_dir / mod_id / "mod_settings.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("target_language_override") or None
    except (json.JSONDecodeError, OSError):
        return None


def save_target_language_override(
    mod_id: str,
    language: str | None,
    *,
    game_id: str,
) -> None:
    """Save the target language override for a mod.

    Args:
        mod_id: Mod's Workshop id.
        language: Language name, or None for default (English).
        game_id: Game the mod belongs to.
    """
    mods_dir = mods_path(game_id)
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / "mod_settings.json"

    existing: dict = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    existing["target_language_override"] = language if language else None
    existing["updated_at"] = datetime.now(UTC).isoformat()

    write_json(path, existing)


def load_include_translated_names(mod_id: str, *, game_id: str) -> bool:
    """Load whether translated names outside the glossary are sent with every prompt.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Saved setting, or False when never saved or unreadable.
    """
    path = mods_path(game_id) / mod_id / "prompt_options.json"
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            return bool(json.load(f).get("include_translated_names", False))
    except (json.JSONDecodeError, OSError, AttributeError):
        return False


def save_include_translated_names(mod_id: str, value: bool, *, game_id: str) -> None:
    """Save whether translated names outside the glossary are sent with every prompt.

    Args:
        mod_id: Mod's Workshop id.
        value: Setting to save.
        game_id: Game the mod belongs to.
    """
    path = mods_path(game_id) / mod_id / "prompt_options.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"include_translated_names": value})
