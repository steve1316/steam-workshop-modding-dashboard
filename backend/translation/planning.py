"""Translate-preview planning shared by every game: prompt previews, cost estimates and the batch plan the frontend loops over."""

from __future__ import annotations

from collections.abc import Callable

from backend.providers.base import TranslationProvider
from backend.translation.prompt import PromptContext


def batch_plan_entry(source_lang: str, chunk: list[tuple[str, str]]) -> dict:
    """Describe one batch for the frontend's translate loop.

    Args:
        source_lang: Language the batch is written in.
        chunk: The batch's (key, source_text) tuples.

    Returns:
        Dict with `source_lang`, `keys` and `size`.
    """
    return {"source_lang": source_lang, "keys": [k for k, _ in chunk], "size": len(chunk)}


def plan_batches(provider: TranslationProvider, chunks_by_lang: dict[str, list[list[tuple[str, str]]]], context_for: Callable[[str], PromptContext]) -> dict:
    """Build the prompt previews, cost estimates and batch plan for already-chunked entries.

    Args:
        provider: Provider that will run the batches.
        chunks_by_lang: Source language -> batches of (key, source_text) tuples.
        context_for: Builds the prompt context for a source language.

    Returns:
        `total_batches`, `previews` and `estimates` keyed by source language, and a flat `batch_plan`.
    """
    previews: dict[str, dict] = {}
    estimates: dict[str, dict] = {}
    batch_plan: list[dict] = []
    for lang, chunks in chunks_by_lang.items():
        kwargs = context_for(lang).provider_kwargs()
        system_prompt = ""
        user_messages: list[str] = []
        for chunk in chunks:
            sp, um = provider.build_prompt(chunk, **kwargs)
            system_prompt = system_prompt or sp
            user_messages.append(um)
        entries = [e for chunk in chunks for e in chunk]
        previews[lang] = {"system_prompt": system_prompt, "user_messages": user_messages, "strings_in_language": len(entries), "batches": len(chunks)}
        estimates[lang] = provider.estimate_cost(entries, **kwargs)
        batch_plan.extend(batch_plan_entry(lang, chunk) for chunk in chunks)
    return {"total_batches": len(batch_plan), "previews": previews, "estimates": estimates, "batch_plan": batch_plan}
