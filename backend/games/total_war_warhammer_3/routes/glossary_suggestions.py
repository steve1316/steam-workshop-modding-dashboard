"""Glossary-suggestion endpoints for WH3: list, scan, suggest-edits, accept and dismiss.

Mounted at the game root so the shared `GlossarySuggestionModal` can POST to `/mods/{id}/glossary/suggestions/{accept,dismiss}` as it does for Chrono Ark.
Suggestions come from the `/translate/batch` loop, Scan for Terms and Suggest Edits, and are persisted via the shared `suggestion_manager`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter

from backend.data import api_response_log, suggestion_manager
from backend.games.total_war_warhammer_3 import GAME_ID
from backend.games.total_war_warhammer_3.adapter import TotalWarWarhammer3Adapter
from backend.games.total_war_warhammer_3.routes import translation as _tr
from backend.games.total_war_warhammer_3.routes.translation import _extract_all_parent_strings, _require_mod
from backend.games.total_war_warhammer_3.stores import glossary as glossary_store
from backend.games.total_war_warhammer_3.stores import snapshots as snapshot_store
from backend.games.total_war_warhammer_3.translation.name_spacing import glossary_words, space_pinyin_names
from backend.providers.claude_provider import ClaudeProvider
from backend.routes.models import SuggestionAction
from backend.translation.suggestions import accepted_suggestions

router = APIRouter(tags=["glossary-suggestions"])


@router.post("/mods/{mod_id}/glossary/suggestions/accept")
def accept_suggestions(mod_id: str, action: SuggestionAction) -> dict:
    """Accept pending glossary suggestions into the mod glossary.

    Moves the specified (or all) suggestions into the glossary after an auto-snapshot. A suggestion with an entry in `action.renames` is saved under
    the edited English, which also replaces the suggested English in every translation whose source contains the term's source.

    Args:
        mod_id: Workshop id of the WH3 mod.
        action: Explicit `terms` or `all`, plus any edited English in `renames`.

    Returns:
        `{"status": "success", "accepted": N, "replaced": M}`, where M counts translations the renames changed.
    """
    mod = _require_mod(mod_id)
    accepted = accepted_suggestions(suggestion_manager.load_suggestions(mod_id, game_id=GAME_ID), action)
    if not accepted:
        return {"status": "success", "accepted": 0, "replaced": 0}
    snapshot_store.create_snapshot(mod_id, label="pre-accept glossary suggestions", kind="auto", local_source_dir=mod.local_source_dir)

    replaced = 0
    for a in accepted:
        entry = {"english": a.english, "source": a.source, "category": a.category}
        if a.edit_of and a.edit_of in glossary_store.load_glossary(mod_id):
            glossary_store.update_term(mod_id, a.edit_of, entry)
        else:
            glossary_store.add_term(mod_id, entry)
        replaced += _tr._rename_in_translations(mod, mod_id, a.source, a.suggested, a.english)

    suggestion_manager.remove_suggestions(mod_id, [a.suggested for a in accepted], game_id=GAME_ID)
    return {"status": "success", "accepted": len({a.suggested for a in accepted}), "replaced": replaced}


@router.post("/mods/{mod_id}/glossary/suggestions/dismiss")
def dismiss_suggestions(mod_id: str, action: SuggestionAction) -> dict:
    """Dismiss pending glossary suggestions without adding them to the glossary.

    Args:
        mod_id: Workshop id of the WH3 mod.
        action: Explicit `terms`, or `all` to clear every pending suggestion.

    Returns:
        `{"status": "success"}`.
    """
    _require_mod(mod_id)
    if action.all:
        suggestion_manager.save_suggestions(mod_id, [], game_id=GAME_ID)
    else:
        suggestion_manager.remove_suggestions(mod_id, action.terms, game_id=GAME_ID)
    return {"status": "success"}


SCAN_SAMPLE_LIMIT = 100
SUGGEST_EDITS_SAMPLE_LIMIT = 25


def _sample_parent_entries(mod, limit: int) -> list[tuple[str, str]]:
    """Take up to `limit` key/source pairs from the parent mods' strings.

    Args:
        mod: Resolved `WH3TranslationMod`.
        limit: Maximum entries.

    Returns:
        `(key, source_text)` pairs.
    """
    entries: list[tuple[str, str]] = []
    for rows in _extract_all_parent_strings(mod).values():
        for key, row in rows.items():
            if len(entries) >= limit:
                return entries
            entries.append((key, row.text))
    return entries


def _ask_claude_for_terms(mod, entries: list[tuple[str, str]], glossary_prompt: str) -> list[dict]:
    """Ask Claude for glossary terms about the given entries, without translating them.

    Args:
        mod: Resolved `WH3TranslationMod`.
        entries: Key/source pairs to show Claude.
        glossary_prompt: Instruction for the suggested terms.

    Returns:
        Claude's suggested terms.
    """
    adapter = TotalWarWarhammer3Adapter()
    _, suggestions = ClaudeProvider().translate_batch(
        entries,
        mod.source_language,
        glossary_prompt=glossary_prompt,
        game_context=adapter.get_translation_context(),
        format_rules=adapter.get_format_preservation_rules(),
        style_examples=adapter.get_style_examples(mod.source_language),
        character_context=None,
        target_lang=mod.target_language,
    )
    return suggestions


def _log_call(mod_id: str, kind: str, keys: list[str], suggestions: list[dict]) -> None:
    """Record a Claude call in the mod's API-responses log.

    Args:
        mod_id: Workshop id of the WH3 mod.
        kind: Log entry kind, e.g. "scan-terms".
        keys: Keys sent.
        suggestions: What Claude returned.
    """
    api_response_log.append(
        mod_id,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": kind,
            "provider": "claude",
            "model": "claude",
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
            "keys_or_inputs": keys,
            "raw_response": json.dumps(suggestions, ensure_ascii=False),
        },
        game_id=GAME_ID,
    )


def _save_new_suggestions(mod_id: str, suggestions: list[dict]) -> int:
    """Save the suggestions that are not already pending or in the glossary.

    Edit suggestions (with `edit_of`) are kept even when their English matches a glossary term.
    Joined pinyin names are split first ("Miaoying" -> "Miao Ying").

    Args:
        mod_id: Workshop id of the WH3 mod.
        suggestions: Candidate suggestions.

    Returns:
        Number newly saved.
    """
    glossary = glossary_store.load_glossary(mod_id)
    glossary_keys = {k.lower() for k in glossary}
    keep = glossary_words(glossary)
    taken = {s.get("english", "").lower() for s in suggestion_manager.load_suggestions(mod_id, game_id=GAME_ID)}
    fresh: list[dict] = []
    for s in suggestions:
        english = space_pinyin_names(s.get("source", ""), s.get("english", ""), keep).strip()
        key = english.lower()
        if not english or key in taken or (key in glossary_keys and not s.get("edit_of")):
            continue
        taken.add(key)
        fresh.append({**s, "english": english})
    if fresh:
        suggestion_manager.add_suggestions(mod_id, fresh, game_id=GAME_ID)
    return len(fresh)


def _mark_edits(mod_id: str, suggestions: list[dict]) -> list[dict]:
    """Link Claude's suggestions to the glossary terms they change, since the provider never sends `edit_of`.

    A suggestion whose English matches a term refines it, and one whose source matches a term under a new English name renames it.
    Both get `edit_of` so accepting updates the term in place. Suggestions identical to their term are dropped.

    Args:
        mod_id: Workshop id of the WH3 mod.
        suggestions: Suggestions from Claude.

    Returns:
        Suggestions worth reviewing, with `edit_of` set where they change a term.
    """
    glossary = glossary_store.load_glossary(mod_id)
    by_english = {k.lower(): k for k in glossary}
    by_source = {v.get("source"): k for k, v in glossary.items() if v.get("source")}
    kept: list[dict] = []
    for s in suggestions:
        english = (s.get("english") or "").strip()
        existing = s.get("edit_of") or by_english.get(english.lower()) or by_source.get(s.get("source"))
        if existing and existing in glossary:
            current = glossary[existing]
            if existing == english and current.get("source") == s.get("source") and current.get("category") == s.get("category"):
                continue
            s = {**s, "edit_of": existing}
        kept.append(s)
    return kept


@router.get("/mods/{mod_id}/glossary/suggestions")
def get_suggestions(mod_id: str) -> list[dict]:
    """List the mod's pending glossary suggestions.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Pending suggestion dicts.
    """
    _require_mod(mod_id)
    return suggestion_manager.load_suggestions(mod_id, game_id=GAME_ID)


@router.post("/mods/{mod_id}/glossary/suggestions/scan")
def scan_for_suggestions(mod_id: str) -> dict:
    """Ask Claude for recurring proper nouns in the parent text and save the new ones as pending suggestions.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{"status": "success", "new": N}`.
    """
    mod = _require_mod(mod_id)
    entries = _sample_parent_entries(mod, SCAN_SAMPLE_LIMIT)
    suggestions = _ask_claude_for_terms(mod, entries, "Identify recurring proper nouns and domain-specific terms via suggested_terms. Do NOT translate.")
    _log_call(mod_id, "scan-terms", [k for k, _ in entries], suggestions)
    return {"status": "success", "new": _save_new_suggestions(mod_id, suggestions)}


@router.post("/mods/{mod_id}/glossary/suggest-edits")
def suggest_edits(mod_id: str) -> dict:
    """Ask Claude for refinements to the current glossary and save them as pending suggestions.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        `{"status": "success", "new": N}`.
    """
    mod = _require_mod(mod_id)
    entries = _sample_parent_entries(mod, SUGGEST_EDITS_SAMPLE_LIMIT)
    glossary_section = json.dumps(glossary_store.load_glossary(mod_id), ensure_ascii=False, indent=2)
    suggestions = _ask_claude_for_terms(mod, entries, f"Current glossary (suggest improvements via suggested_terms only):\n{glossary_section}")
    _log_call(mod_id, "suggest-edits", [k for k, _ in entries], suggestions)
    return {"status": "success", "new": _save_new_suggestions(mod_id, _mark_edits(mod_id, suggestions))}
