"""Glossary endpoints for the REST API."""

from fastapi import APIRouter

from backend.core.paths import glossary_path
from backend.games.chrono_ark import GAME_ID
from backend.persistence.glossary_manager import (
    add_glossary_term,
    extract_name_key_suggestions,
    load_glossary,
    load_mod_glossary,
    merge_glossaries,
    save_glossary,
    save_mod_glossary,
    suggest_glossary_edits,
)
from backend.persistence.history_manager import create_backup
from backend.persistence.mod_settings import load_source_language_override, load_target_language_override
from backend.persistence.suggestion_manager import (
    add_suggestions,
    load_suggestions,
    remove_suggestions,
    save_suggestions,
)
from backend.persistence.translation_store import load_translations, save_translations_bulk
from backend.routes.helpers import _find_mod_path, _merge_gdata_originals, chrono_ark_adapter, resolve_source_language
from backend.routes.models import (
    GlossaryTerm,
    ModGlossaryTerm,
    SuggestionAction,
)
from backend.translation.rename import rename_term
from backend.translation.suggestions import accepted_suggestions

router = APIRouter()


@router.get("/glossary")
def get_glossary():
    """Get the global glossary.

    Returns:
        Glossary dict as stored on disk, with a `terms` mapping.
    """
    glossary = load_glossary(glossary_path(GAME_ID))
    return glossary


@router.post("/glossary")
def update_glossary(term: GlossaryTerm):
    """Add or update a glossary term.

    Args:
        term: Source text and its English.

    Returns:
        `{"status": "success"}`.
    """
    glossary = load_glossary(glossary_path(GAME_ID))
    add_glossary_term(glossary, term.english, {"custom": term.source})
    save_glossary(glossary, glossary_path(GAME_ID))
    return {"status": "success"}


@router.get("/mods/{mod_id}/glossary")
def get_mod_glossary(mod_id: str):
    """Get a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Glossary dict with a `terms` mapping.
    """
    return load_mod_glossary(mod_id, game_id=GAME_ID)


@router.post("/mods/{mod_id}/glossary")
def update_mod_glossary(mod_id: str, term: ModGlossaryTerm):
    """Add or update a term in a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.
        term: English, per-language source mappings, and category.

    Returns:
        `{"status": "success"}`.
    """
    create_backup(mod_id, f"Before adding glossary term '{term.english}'", game_id=GAME_ID)
    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    add_glossary_term(glossary, term.english, term.source_mappings, term.category)
    save_mod_glossary(mod_id, glossary, game_id=GAME_ID)
    return {"status": "success"}


def _find_term_key(terms: dict, term: str) -> str | None:
    """Find a mod glossary entry's key from its key or its English.

    Terms with source text are keyed by that text, while the frontend refers to terms by their English.

    Args:
        terms: Glossary `terms` dict.
        term: Entry's key or English.

    Returns:
        Matching key, or None.
    """
    if term in terms:
        return term
    return next((key for key, info in terms.items() if info.get("english") == term), None)


@router.put("/mods/{mod_id}/glossary/{term:path}")
def edit_mod_glossary_term(mod_id: str, term: str, entry: ModGlossaryTerm):
    """Replace a mod glossary term with edited values.

    A new English also replaces the old English in every translation whose source contains one of the term's old source texts.

    Args:
        mod_id: Mod's Workshop id.
        term: Existing term's key or English.
        entry: Edited English, source mappings, and category.

    Returns:
        `status` and the `replaced` translation count.
    """
    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    terms = glossary.setdefault("terms", {})
    key = _find_term_key(terms, term)
    old = terms.pop(key) if key else {}
    create_backup(mod_id, f"Before editing glossary term '{term}'", game_id=GAME_ID)
    add_glossary_term(glossary, entry.english, entry.source_mappings, entry.category)
    save_mod_glossary(mod_id, glossary, game_id=GAME_ID)

    old_english = old.get("english") or term
    replaced = 0
    if old and entry.english != old_english:
        for source in set((old.get("source_mappings") or {}).values()):
            replaced += _rename_in_translations(mod_id, source, old_english, entry.english)
    return {"status": "success", "replaced": replaced}


@router.delete("/mods/{mod_id}/glossary/{term:path}")
def delete_mod_glossary_term(mod_id: str, term: str):
    """Remove a term from a mod's glossary (no-op if it doesn't exist).

    Args:
        mod_id: Mod's Workshop id.
        term: Term's key or English.

    Returns:
        `{"status": "success"}`.
    """
    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    key = _find_term_key(glossary.get("terms", {}), term)
    if key:
        create_backup(mod_id, f"Before removing glossary term '{term}'", game_id=GAME_ID)
        del glossary["terms"][key]
        save_mod_glossary(mod_id, glossary, game_id=GAME_ID)
    return {"status": "success"}


@router.post("/mods/{mod_id}/glossary/delete")
def delete_mod_glossary_terms(mod_id: str, action: SuggestionAction):
    """Remove specific terms or all terms from a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.
        action: Terms to delete, or `all`.

    Returns:
        `status` and the `deleted` count.
    """
    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    terms = glossary.get("terms", {})
    if action.all:
        count = len(terms)
        if count > 0:
            create_backup(mod_id, "Before deleting all glossary terms", game_id=GAME_ID)
        glossary["terms"] = {}
    else:
        count = 0
        for term in action.terms:
            key = _find_term_key(terms, term)
            if key:
                if count == 0:
                    create_backup(mod_id, "Before removing glossary term(s)", game_id=GAME_ID)
                del terms[key]
                count += 1
    save_mod_glossary(mod_id, glossary, game_id=GAME_ID)
    return {"status": "success", "deleted": count}


@router.delete("/mods/{mod_id}/glossary")
def delete_all_mod_glossary_terms(mod_id: str):
    """Remove all terms from a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status` and the `deleted` count.
    """
    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    count = len(glossary.get("terms", {}))
    if count > 0:
        create_backup(mod_id, "Before deleting all glossary terms", game_id=GAME_ID)
    glossary["terms"] = {}
    save_mod_glossary(mod_id, glossary, game_id=GAME_ID)
    return {"status": "success", "deleted": count}


@router.get("/mods/{mod_id}/glossary/merged")
def get_merged_glossary(mod_id: str):
    """Get the global glossary merged with the mod's, mod terms winning on conflicts.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Merged glossary for translation prompts.
    """
    base = load_glossary(glossary_path(GAME_ID))
    mod = load_mod_glossary(mod_id, game_id=GAME_ID)
    return merge_glossaries(base, mod)


@router.get("/mods/{mod_id}/glossary/suggestions")
def get_suggestions(mod_id: str):
    """Get pending glossary term suggestions.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        Suggestion dicts with `english`, `source`, `source_lang`, `category`.
    """
    return load_suggestions(mod_id, game_id=GAME_ID)


def _source_and_csv_english(mod_id: str) -> dict[str, tuple[str, str]]:
    """Read each string's source text and the English in the mod's own files, the same way the Details page does.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `{key: (source text, English from the mod's files)}`.
    """
    strings, _ = chrono_ark_adapter().extract_strings(_find_mod_path(mod_id))
    target_lang = load_target_language_override(mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(mod_id, strings, target_lang=target_lang)
    override = load_source_language_override(mod_id, game_id=GAME_ID)
    rows: dict[str, tuple[str, str]] = {}
    for key, loc_str in strings.items():
        source_lang = resolve_source_language(loc_str, override)
        rows[key] = (loc_str.translations.get(source_lang, "") if source_lang else "", loc_str.translations.get(target_lang, ""))
    return rows


def _rename_in_translations(mod_id: str, source: str, old_english: str, new_english: str) -> int:
    """Rename `old_english` to `new_english` in every translation whose source text contains `source`.

    A row with no saved translation uses the English in the mod's files, so it is renamed too and saved as an edit.

    Args:
        mod_id: Mod's Workshop id.
        source: Term's source text (nothing is renamed when empty).
        old_english: English to replace, matched as a whole term.
        new_english: Replacement English.

    Returns:
        Count of changed translations.
    """
    if not source or old_english == new_english:
        return 0
    saved = load_translations(mod_id, game_id=GAME_ID)
    rows = ((key, source_text, saved.get(key, csv_english)) for key, (source_text, csv_english) in _source_and_csv_english(mod_id).items())
    changes = rename_term(rows, old_english, new_english, source)
    if changes:
        save_translations_bulk(mod_id, changes, game_id=GAME_ID)
    return len(changes)


@router.post("/mods/{mod_id}/glossary/suggestions/accept")
def accept_suggestions(mod_id: str, action: SuggestionAction):
    """Accept suggestions into the mod glossary.

    A suggestion with an entry in `action.renames` is saved under the edited English, which also replaces the suggested English in every translation
    whose source contains the term's source.

    Args:
        mod_id: Mod's Workshop id.
        action: Suggestions to accept (or `all`), plus any edited English in `renames`.

    Returns:
        `status`, the `accepted` count, and the `replaced` translation count.
    """
    accepted = accepted_suggestions(load_suggestions(mod_id, game_id=GAME_ID), action)
    if not accepted:
        return {"status": "success", "accepted": 0, "replaced": 0}
    create_backup(mod_id, "Before accepting glossary suggestions", game_id=GAME_ID)

    glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    replaced = 0
    for a in accepted:
        if a.edit_of and a.edit_of in glossary.get("terms", {}):
            del glossary["terms"][a.edit_of]
        add_glossary_term(glossary, a.english, {a.source_lang: a.source}, a.category)
        replaced += _rename_in_translations(mod_id, a.source, a.suggested, a.english)

    save_mod_glossary(mod_id, glossary, game_id=GAME_ID)
    remove_suggestions(mod_id, [a.suggested for a in accepted], game_id=GAME_ID)
    return {"status": "success", "accepted": len({a.suggested for a in accepted}), "replaced": replaced}


@router.post("/mods/{mod_id}/glossary/suggestions/dismiss")
def dismiss_suggestions(mod_id: str, action: SuggestionAction):
    """Remove suggestions without adding them to the glossary.

    Args:
        mod_id: Mod's Workshop id.
        action: Suggestions to dismiss, or `all`.

    Returns:
        `{"status": "success"}`.
    """
    if action.all:
        save_suggestions(mod_id, [], game_id=GAME_ID)
    else:
        remove_suggestions(mod_id, action.terms, game_id=GAME_ID)
    return {"status": "success"}


@router.post("/mods/{mod_id}/glossary/suggestions/scan")
def scan_for_suggestions(mod_id: str):
    """Run `extract_name_key_suggestions` over all already-translated strings, without triggering a translation run.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status` and the `new` suggestion count.
    """
    mod_path = _find_mod_path(mod_id)
    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(mod_id, strings)

    saved = load_translations(mod_id, game_id=GAME_ID)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations["English"] = english

    lang_override = load_source_language_override(mod_id, game_id=GAME_ID)
    mod_glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    existing_suggestions = load_suggestions(mod_id, game_id=GAME_ID)

    translations: dict[str, str] = {}
    by_lang: dict[str, list[str]] = {}
    for key, loc_str in strings.items():
        english = loc_str.translations.get("English", "").strip()
        if not english:
            continue
        source_lang = resolve_source_language(loc_str, lang_override)
        if not source_lang:
            continue
        translations[key] = english
        by_lang.setdefault(source_lang, []).append(key)

    new_suggestions: list[dict] = []
    combined_existing = existing_suggestions + new_suggestions
    for lang, keys in by_lang.items():
        found = extract_name_key_suggestions(
            translated_keys=keys,
            strings=strings,
            translations=translations,
            source_lang=lang,
            existing_suggestions=combined_existing,
            mod_glossary=mod_glossary,
            term_categories=chrono_ark_adapter().get_glossary_categories(),
        )
        new_suggestions.extend(found)
        combined_existing.extend(found)

    if new_suggestions:
        add_suggestions(mod_id, new_suggestions, game_id=GAME_ID)

    return {"status": "success", "new": len(new_suggestions)}


@router.post("/mods/{mod_id}/glossary/suggest-edits")
def suggest_edits(mod_id: str):
    """Suggest edits for name-category glossary terms that aren't title-cased.

    Args:
        mod_id: Mod's Workshop id.

    Returns:
        `status` and the `new` edit suggestion count.
    """
    mod_glossary = load_mod_glossary(mod_id, game_id=GAME_ID)
    existing_suggestions = load_suggestions(mod_id, game_id=GAME_ID)

    edits = suggest_glossary_edits(mod_glossary, existing_suggestions)

    if edits:
        add_suggestions(mod_id, edits, game_id=GAME_ID)

    return {"status": "success", "new": len(edits)}
