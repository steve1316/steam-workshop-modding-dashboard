"""Filesystem path helpers, including per-game storage under `<STORAGE_PATH>/games/<game_id>`.

Legacy flat storage is migrated into this layout by `backend.scripts.migrate_storage_v1_to_v2` at startup.
"""

from __future__ import annotations

from pathlib import Path

from backend import config


def safe_child(base: Path, name: str) -> Path:
    """Join a single user-supplied name onto `base`, rejecting anything that could point outside it.

    Args:
        base: The directory the name must stay inside.
        name: A bare file or folder name, such as a backup id from a URL.

    Returns:
        The joined path.
    """
    # Backslashes and drive colons matter too, since Windows treats them as separators.
    if name in ("", ".", "..") or any(c in name for c in "/\\:"):
        raise ValueError(f"Invalid name: {name!r}")
    return base / name


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


class GameStorage:
    """Resolves per-game, per-mod storage paths under a single game root."""

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id

    @property
    def root(self) -> Path:
        """Return the per-game storage root."""
        return game_storage_path(self.game_id)

    @property
    def mods_dir(self) -> Path:
        """Return the per-game mods directory."""
        return self.root / "mods"

    def mod_dir(self, mod_id: str) -> Path:
        """Return the storage directory for a single mod.

        Args:
            mod_id: Mod's Workshop id.

        Returns:
            `<root>/mods/<mod_id>`.
        """
        return self.mods_dir / mod_id

    def mod_file(self, mod_id: str, filename: str) -> Path:
        """Return the path to a per-mod sidecar file.

        Args:
            mod_id: Mod's Workshop id.
            filename: Sidecar file name, e.g. `"synced_keys.json"`.

        Returns:
            `<root>/mods/<mod_id>/<filename>`.
        """
        return self.mod_dir(mod_id) / filename
