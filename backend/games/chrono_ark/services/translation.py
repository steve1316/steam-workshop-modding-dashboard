"""Chrono Ark translation services shared by the routes and the CLI: loading a mod's strings, its prompt context and saving a batch."""

from backend.core.paths import glossary_path
from backend.games.chrono_ark import GAME_ID
from backend.models import LocString
from backend.persistence.character_context import load_character_context
from backend.persistence.glossary_manager import extract_name_key_suggestions, get_combined_glossary_prompt, load_glossary, load_mod_glossary
from backend.persistence.mod_settings import load_target_language_override
from backend.persistence.progress_tracker import ProgressTracker
from backend.persistence.suggestion_manager import add_suggestions, load_suggestions
from backend.persistence.translation_memory import TranslationMemory
from backend.persistence.translation_store import load_translations, save_translations_bulk
from backend.routes.helpers import _filter_suggestions, _find_mod_path, _merge_gdata_originals, chrono_ark_adapter
from backend.translation.pipeline import BatchOutcome, PersistHook
from backend.translation.prompt import PromptContext


def load_mod_strings(mod_id: str) -> tuple[dict[str, LocString], str]:
    """Extract a mod's strings with gdata originals restored and saved translations overlaid, so user edits (including clears) win.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        (key -> string, the mod's target language).
    """
    strings, _ = chrono_ark_adapter().extract_strings(_find_mod_path(mod_id))
    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)
    for key, text in load_translations(mod_id, game_id=GAME_ID).items():
        if key in strings:
            strings[key].translations[target_lang] = text
    return strings, target_lang


def batch_entries(strings: dict[str, LocString], keys: list[str], source_lang: str) -> list[tuple[str, str]]:
    """Pick the requested keys that have source text in `source_lang`.

    Args:
        strings: The mod's strings.
        keys: Keys the batch asked for.
        source_lang: Language to read the source text from.

    Returns:
        (key, source_text) tuples, in request order.
    """
    return [(key, text) for key in keys if key in strings and (text := strings[key].translations.get(source_lang, ""))]


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


def persist_batch(mod_id: str, provider_name: str, strings: dict[str, LocString], entries: list[tuple[str, str]], source_lang: str) -> PersistHook:
    """Build the hook that saves a Chrono Ark batch: translation memory, translations, progress, then the suggestions worth reviewing.

    Args:
        mod_id: Mod's Workshop id.
        provider_name: Provider id recorded on the saved rows.
        strings: The mod's strings, for suggestion filtering and name-key terms.
        entries: The batch's (key, source_text) tuples.
        source_lang: Language the batch was written in.

    Returns:
        The persistence hook.
    """

    def persist(translations: dict[str, str], suggestions: list[dict]) -> BatchOutcome:
        tm = TranslationMemory(game_id=GAME_ID)
        sources = dict(entries)
        for key, text in translations.items():
            if sources.get(key) and text:
                tm.store(sources[key], text, source_lang)
        save_translations_bulk(mod_id, translations, game_id=GAME_ID, provider=provider_name)
        ProgressTracker(game_id=GAME_ID).mark_translated(mod_id, list(translations))
        tm.save()

        kept = _filter_suggestions(suggestions, strings)
        # Name-key terms the provider didn't already suggest.
        kept.extend(
            extract_name_key_suggestions(
                translated_keys=list(translations),
                strings=strings,
                translations=translations,
                source_lang=source_lang,
                existing_suggestions=load_suggestions(mod_id, game_id=GAME_ID) + kept,
                mod_glossary=load_mod_glossary(mod_id, game_id=GAME_ID),
                term_categories=chrono_ark_adapter().get_glossary_categories(),
            )
        )
        if kept:
            add_suggestions(mod_id, kept, game_id=GAME_ID)
        return BatchOutcome(translations, kept)

    return persist
