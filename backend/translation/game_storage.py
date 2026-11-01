"""Per-game storage path facade. Callers must never join `config.STORAGE_PATH` directly."""

from __future__ import annotations

from pathlib import Path

from backend.games.storage_paths import game_storage_path


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
