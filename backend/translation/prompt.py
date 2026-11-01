"""The context every provider call is built from besides its entries: languages, glossary, game rules and style examples."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.games.capabilities.translation import TranslationCapability


@dataclass(frozen=True)
class PromptContext:
    """Prompt inputs shared by `build_prompt`, `translate_batch` and `estimate_cost`.

    Attributes:
        source_lang: Language the entries are written in, e.g. `"Korean"`.
        target_lang: Language to translate into.
        glossary_prompt: Formatted glossary section.
        game_context: Game description for the system prompt.
        format_rules: Game-specific formatting preservation rules.
        style_examples: Category -> [(source, target)] pairs.
        character_context: Character background, or None when the mod has none.
    """

    source_lang: str
    target_lang: str
    glossary_prompt: str
    game_context: str = ""
    format_rules: list[str] = field(default_factory=list)
    style_examples: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    character_context: dict | None = None

    @classmethod
    def for_adapter(cls, adapter: TranslationCapability, source_lang: str, target_lang: str, glossary_prompt: str, character_context: dict | None = None) -> PromptContext:
        """Build a context from a game adapter's translation context, format rules and style examples.

        Args:
            adapter: Game adapter supplying the game-specific parts.
            source_lang: Source language name.
            target_lang: Target language name.
            glossary_prompt: Formatted glossary section.
            character_context: Character background, if any.

        Returns:
            The context.
        """
        return cls(
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_prompt=glossary_prompt,
            game_context=adapter.get_translation_context(),
            format_rules=adapter.get_format_preservation_rules(),
            style_examples=adapter.get_style_examples(source_lang),
            character_context=character_context,
        )

    def provider_kwargs(self) -> dict:
        """Return the keyword arguments every provider prompt method takes.

        Returns:
            Dict of keyword arguments.
        """
        return {
            "source_lang": self.source_lang,
            "glossary_prompt": self.glossary_prompt,
            "game_context": self.game_context,
            "format_rules": self.format_rules,
            "style_examples": self.style_examples,
            "character_context": self.character_context,
            "target_lang": self.target_lang,
        }
