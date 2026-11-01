"""Per-mod glossary CRUD wrappers for the WH3 translation flow.

Stores `<root>/mods/{id}/glossary.json` as a flat dict keyed by English term. The shared `backend.data.glossary_manager` handles disk IO
with a `{"terms": {...}}` wrapper, which this module pins to the WH3 game id and flattens. It also holds the apply-rename helper.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.core.json_store import write_json
from backend.data import glossary_manager as gm
from backend.games.storage_paths import game_storage_path, glossary_path

GAME_ID = "total_war_warhammer_3"


def _root() -> Path:
    return game_storage_path(GAME_ID)


def load_glossary(mod_id: str) -> dict:
    """Load the per-mod glossary as `{english_term: {source, category}}`.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Glossary dict, empty when no file exists.
    """
    raw = gm.load_mod_glossary(mod_id, storage_path=_root())
    return dict(raw.get("terms", {}))


def _save(mod_id: str, glossary: dict) -> None:
    gm.save_mod_glossary(mod_id, {"terms": glossary}, storage_path=_root())


def add_term(mod_id: str, entry: dict) -> None:
    """Add or replace a glossary entry.

    Args:
        mod_id: Workshop id of the WH3 mod.
        entry: `{english, source, category}`, keyed by `english`.
    """
    english = entry.get("english")
    if not english:
        raise ValueError("entry must include 'english'")
    glossary = load_glossary(mod_id)
    glossary[english] = {"source": entry.get("source", ""), "category": entry.get("category", "")}
    _save(mod_id, glossary)


def update_term(mod_id: str, old_english: str, entry: dict) -> None:
    """Update an entry, removing the old key when `entry["english"]` differs from `old_english`.

    Args:
        mod_id: Workshop id of the WH3 mod.
        old_english: Current English term key.
        entry: Updated `{english, source, category}`.
    """
    new_english = entry.get("english")
    if not new_english:
        raise ValueError("entry must include 'english'")
    glossary = load_glossary(mod_id)
    if old_english in glossary and old_english != new_english:
        del glossary[old_english]
    glossary[new_english] = {"source": entry.get("source", ""), "category": entry.get("category", "")}
    _save(mod_id, glossary)


def delete_term(mod_id: str, english: str) -> None:
    """Remove a glossary entry by English term.

    Args:
        mod_id: Workshop id of the WH3 mod.
        english: English term key to delete.
    """
    glossary = load_glossary(mod_id)
    glossary.pop(english, None)
    _save(mod_id, glossary)


def delete_all_terms(mod_id: str) -> int:
    """Remove every entry from the per-mod glossary.

    Args:
        mod_id: Workshop id of the WH3 mod.

    Returns:
        Number of terms removed.
    """
    count = len(load_glossary(mod_id))
    _save(mod_id, {})
    return count


def apply_term_rename(mod_id: str, old_english: str, new_english: str) -> int:
    """Word-boundary find-and-replace `old_english` -> `new_english` across all translations.

    Args:
        mod_id: Workshop id of the WH3 mod.
        old_english: Previous English term.
        new_english: Replacement term.

    Returns:
        Total replacements made.
    """
    path = _root() / "mods" / mod_id / "translations.json"
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    pattern = re.compile(r"\b" + re.escape(old_english) + r"\b")
    total = 0
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        text = entry.get("text") or ""
        new_text, count = pattern.subn(new_english, text)
        if count > 0 and new_text != text:
            entry["text"] = new_text
            total += count

    write_json(path, raw)
    return total


def load_base_glossary() -> dict:
    """Load the WH3 base-game glossary as `{"terms": {...}}`.

    Returns:
        Base glossary, `{"terms": {}}` when not built yet.
    """
    return gm.load_glossary(glossary_path(GAME_ID))


def mod_glossary_as_terms(mod_id: str, source_language: str) -> dict:
    """Adapt the flat per-mod glossary into the `{"terms": {...}}` shape used by the prompt builder.

    Args:
        mod_id: Workshop id of the WH3 mod.
        source_language: Mod's source language, used as the `source_mappings` key.

    Returns:
        `{"terms": {english: {english, category, key, source_mappings}}}`.
    """
    flat = load_glossary(mod_id)
    terms: dict[str, dict] = {}
    for english, info in flat.items():
        source = info.get("source", "")
        terms[english] = {
            "english": english,
            "category": info.get("category", ""),
            "key": "",
            "source_mappings": {source_language: source} if source else {},
        }
    return {"terms": terms}
