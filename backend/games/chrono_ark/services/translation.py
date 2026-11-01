"""Chrono Ark translation inputs: the prompt context a mod's batches are built from."""

from backend.core.paths import glossary_path
from backend.data.character_context import load_character_context
from backend.data.glossary_manager import get_combined_glossary_prompt, load_glossary, load_mod_glossary
from backend.games.chrono_ark import GAME_ID
from backend.routes.helpers import chrono_ark_adapter
from backend.translation.prompt import PromptContext


def prompt_context(mod_id: str, source_lang: str, target_lang: str, *, base_glossary: dict | None = None) -> PromptContext:
    """Build the prompt context for one mod and source language, with the base + mod glossary and the mod's character background.

    Args:
        mod_id: Mod's Workshop id.
        source_lang: Source language name.
        target_lang: Target language name.
        base_glossary: Already-loaded base glossary, to skip reloading it for every mod.

    Returns:
        The context.
    """
    base = base_glossary if base_glossary is not None else load_glossary(glossary_path(GAME_ID))
    glossary_prompt = get_combined_glossary_prompt(base, load_mod_glossary(mod_id, game_id=GAME_ID), source_lang=source_lang, target_lang=target_lang)
    char_ctx = load_character_context(mod_id, game_id=GAME_ID)
    return PromptContext.for_adapter(chrono_ark_adapter(), source_lang, target_lang, glossary_prompt, character_context=char_ctx if any(char_ctx.values()) else None)
