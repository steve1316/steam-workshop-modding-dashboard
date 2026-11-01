"""Translation capability mixin for adapters that extract and translate strings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.games.base import ModInfo
    from backend.models import LocString


class TranslationCapability(ABC):
    """Mixin declaring translation-related operations, inherited alongside `GameAdapter`.

    Callers should check `isinstance(adapter, TranslationCapability)` or the adapter's `capabilities` list.
    """

    @property
    @abstractmethod
    def target_language(self) -> str:
        """Return the language strings are translated INTO (e.g. `"English"`)."""

    @property
    @abstractmethod
    def source_languages(self) -> list[str]:
        """Return source-language column names in detection-priority order."""

    @abstractmethod
    def get_translation_context(self) -> str:
        """Return prose context injected into translation prompts."""

    @abstractmethod
    def get_format_preservation_rules(self) -> list[str]:
        """Return per-line format rules appended to system prompts."""

    @abstractmethod
    def get_style_examples(self, source_lang: str = "Korean") -> dict[str, list[tuple[str, str]]]:
        """Return source-language to list of (input, output) example pairs."""

    @abstractmethod
    def get_base_glossary_prompt(self, source_lang: str, target_lang: str = "English") -> str:
        """Return the base-game glossary section for translation prompts.

        Each adapter filters to its own prompt categories so the system-prompt preview matches what is actually sent.

        Args:
            source_lang: Source language to include (e.g. `"Chinese"`).
            target_lang: Language translated into.

        Returns:
            Glossary section, or `""` when no terms match.
        """

    @abstractmethod
    def scan_mods(self, search_path: Path | None = None) -> list[ModInfo]:
        """Return discovered mods at `search_path` (or default workshop path)."""

    @abstractmethod
    def extract_strings(self, mod_path: Path) -> tuple[dict[str, LocString], list[str]]:
        """Extract localizable strings from `mod_path`.

        Args:
            mod_path: Mod directory.

        Returns:
            `(strings keyed by stable id, warnings)`.
        """

    @property
    @abstractmethod
    def base_game_path(self) -> Path | None:
        """Return the on-disk base-game path, or `None` if not configured."""

    @abstractmethod
    def extract_base_game_strings(self, game_path: Path | None = None) -> dict[str, LocString]:
        """Extract base-game strings from `game_path` (defaults to `base_game_path`)."""

    @abstractmethod
    def detect_source_language(self, loc_string: LocString) -> str | None:
        """Auto-detect the source language of `loc_string`."""

    @abstractmethod
    def get_untranslated(self, strings: dict[str, LocString]) -> dict[str, LocString]:
        """Filter `strings` down to entries lacking a target-language translation."""

    @abstractmethod
    def get_glossary_categories(self) -> dict[str, str | list[str]]:
        """Return category-name to file-or-directory hints for glossary auto-build."""

    @abstractmethod
    def export_strings(self, output_path: Path, entries: list[LocString]) -> None:
        """Write `entries` to `output_path` in the game's native format."""

    @abstractmethod
    def get_mod_url(self, mod_id: str) -> str | None:
        """Return a public URL for `mod_id` (e.g. Steam Workshop link)."""

    def get_translation_overrides_dir(self) -> Path | None:
        """Return the injector's overrides directory, or `None` when the adapter has no injector."""
        return None
