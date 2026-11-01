"""Game-agnostic batch-translation helpers. Storage, progress and glossary suggestions stay in each game's route layer."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.translation.prompt import PromptContext


def fill_duplicate_translations(translations: dict[str, str], entries: list[tuple[str, str]]) -> dict[str, str]:
    """Fill missing keys whose source text matches an already-translated entry.

    LLMs often deduplicate identical source strings and return only one key.

    Args:
        translations: Provider's key -> target text, modified in place.
        entries: Original (key, source_text) tuples sent to the provider.

    Returns:
        The same `translations` dict.
    """
    source_to_translation: dict[str, str] = {}
    for key, source_text in entries:
        if key in translations:
            source_to_translation[source_text] = translations[key]

    for key, source_text in entries:
        if key not in translations and source_text in source_to_translation:
            translations[key] = source_to_translation[source_text]

    return translations


def chunk_entries(entries: list[tuple[str, str]], max_keys: int, max_chars: int) -> list[list[tuple[str, str]]]:
    """Split entries into batches capped by key count and by total source characters.

    The character cap keeps the model's reply within its output token limit. An entry longer than `max_chars` still gets a batch of its own.

    Args:
        entries: (key, source_text) tuples in translation order.
        max_keys: Most entries allowed in one batch.
        max_chars: Most source characters allowed in one batch.

    Returns:
        The batches, in order.
    """
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_chars = 0
    for key, text in entries:
        size = len(text or "")
        if current and (len(current) >= max_keys or current_chars + size > max_chars):
            chunks.append(current)
            current, current_chars = [], 0
        current.append((key, text))
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


async def run_batch(provider: Any, entries: list[tuple[str, str]], context: PromptContext) -> tuple[dict[str, str], list[Any]]:
    """Translate one batch via `provider` in the default executor, then fill deduplicated keys.

    Args:
        provider: Provider exposing `translate_batch(...)`.
        entries: (key, source_text) tuples.
        context: Languages, glossary and game rules for the prompt.

    Returns:
        (translations keyed by key, suggestion objects).
    """
    loop = asyncio.get_running_loop()
    translations, suggestions = await loop.run_in_executor(None, lambda: provider.translate_batch(entries, **context.provider_kwargs()))
    fill_duplicate_translations(translations, entries)
    return translations, suggestions
