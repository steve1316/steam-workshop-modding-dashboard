"""Per-mod pending glossary suggestions from AI providers, kept until the user accepts or dismisses them."""

import json
import re
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path

_TAG_RE = re.compile(r"<[^>]+>")


def load_suggestions(mod_id: str, storage_path: Path | None = None) -> list[dict]:
    """Load pending suggestions for a mod.

    Args:
        mod_id: Mod's Workshop id.
        storage_path: Storage root override.

    Returns:
        Suggestion dicts, empty if none.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "pending_suggestions.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_suggestions(mod_id: str, suggestions: list[dict], storage_path: Path | None = None) -> None:
    """Save pending suggestions for a mod.

    Args:
        mod_id: Mod's Workshop id.
        suggestions: Suggestion dicts to persist.
        storage_path: Storage root override.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "pending_suggestions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, suggestions)


def add_suggestions(mod_id: str, new_suggestions: list[dict], storage_path: Path | None = None) -> None:
    """Append new suggestions, deduplicating by english term.

    Existing suggestions with the same english term are kept, not overwritten.

    Args:
        mod_id: Mod's Workshop id.
        new_suggestions: Suggestion dicts, each with at least an `english` key.
        storage_path: Storage root override.
    """
    existing = load_suggestions(mod_id, storage_path)
    existing_terms = {_TAG_RE.sub("", s["english"]).lower() for s in existing if "english" in s}
    for suggestion in new_suggestions:
        term = suggestion.get("english", "")
        stripped = _TAG_RE.sub("", term).lower()
        if term and stripped not in existing_terms:
            existing.append(suggestion)
            existing_terms.add(stripped)
    save_suggestions(mod_id, existing, storage_path)


def remove_suggestions(mod_id: str, terms: list[str], storage_path: Path | None = None) -> None:
    """Remove suggestions by english term.

    Args:
        mod_id: Mod's Workshop id.
        terms: English terms to remove.
        storage_path: Storage root override.
    """
    existing = load_suggestions(mod_id, storage_path)
    filtered = [s for s in existing if s.get("english") not in terms]
    save_suggestions(mod_id, filtered, storage_path)
