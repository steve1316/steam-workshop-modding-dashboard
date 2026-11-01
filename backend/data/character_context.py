"""Load and save per-mod character context for translation prompts."""

import json
from datetime import UTC, datetime

from backend.core.json_store import write_json
from backend.core.paths import mods_path

_DEFAULTS = {"source_game": "", "character_name": "", "background": "", "created_at": "", "updated_at": ""}


def load_character_context(mod_id: str, *, game_id: str) -> dict:
    """Return a mod's character context, with empty-string defaults for missing fields.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Dict with `source_game`, `character_name` and `background`.
    """
    mods_dir = mods_path(game_id)
    path = mods_dir / mod_id / "character_context.json"
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: data.get(k, "") for k in _DEFAULTS}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_character_context(mod_id: str, ctx: dict, *, game_id: str) -> None:
    """Save a mod's character context, persisting only the `_DEFAULTS` keys.

    Args:
        mod_id: Mod's Workshop id.
        ctx: Character context to save.
        game_id: Game the mod belongs to.
    """
    mods_dir = mods_path(game_id)
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / "character_context.json"

    # Preserve existing created_at if the file already exists.
    existing = load_character_context(mod_id, game_id=game_id)
    now = datetime.now(UTC).isoformat()

    data = {k: ctx.get(k, "") for k in _DEFAULTS}
    data["created_at"] = existing["created_at"] if existing["created_at"] else now
    data["updated_at"] = now

    write_json(path, data)
