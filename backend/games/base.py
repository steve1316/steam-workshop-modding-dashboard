"""Abstract base class for game adapters, plus the game-agnostic `ModInfo`."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass
class ModInfo:
    """Game-agnostic mod/project metadata."""

    mod_id: str
    name: str = ""
    author: str = ""
    has_loc_files: bool = False
    has_dll: bool = False
    loc_file_paths: list[Path] = field(default_factory=list)
    dll_paths: list[Path] = field(default_factory=list)
    entry_count: int = 0
    target_lang_populated: bool = False
    path: Path = field(default_factory=lambda: Path("."))


class GameAdapter(ABC):
    """Base interface for game adapters.

    Domain operations come from capability mixins in `backend.games.capabilities` (e.g. `TranslationCapability`).
    """

    @property
    @abstractmethod
    def game_id(self) -> str:
        """Return the unique adapter id (e.g. `"chrono_ark"`)."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return the human-readable game name shown in the UI."""

    @property
    @abstractmethod
    def icon(self) -> str:
        """Return the icon key or asset path for the game."""

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """Return capability tags (e.g. `["translation", "pack_assembly"]`)."""

    @property
    @abstractmethod
    def router(self) -> "APIRouter":
        """Return the FastAPI router mounted at `/api/games/<game_id>/...`."""

    @property
    def settings_schema(self) -> dict[str, dict]:
        """Return the per-game settings schema.

        Returns:
            Mapping of setting key to `{"type": <python type name>, "default": <value>}`.
        """
        return {}

    def on_register(self) -> None:
        """Hook called once when the adapter is registered. Default: no-op."""

    @property
    def game_name(self) -> str:
        """Back-compat alias for `display_name`."""
        return self.display_name
