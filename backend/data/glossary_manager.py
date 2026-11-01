"""Glossary of canonical English game terms built from the base game's localization, with per-mod glossaries layered on top."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path
from backend.core.settings import settings
from backend.models import LocString

_NAME_KEY_SUFFIXES = ("_Name", "_name", "_PassiveName", "_SkinName")

# Prefixes of keys whose English value is a mechanic term name.
_MECHANIC_PREFIXES = ("Battle/Keyword/", "Battle/SkillTooltip/")

_MECHANIC_EXACT_KEYS: dict[str, str] = {
    "System/Debuff": "Debuff",
    "UI/CharStat/PartyStat_MP": "Mana",
    "UI/Battle/Buff/Barrier": "Barrier",
}

# Mechanic terms that appear inside other strings with no dedicated key, mapped to their source language forms.
_MANUAL_MECHANIC_TERMS: dict[str, dict[str, str]] = {
    "Exchange": {"Chinese": "交换", "Korean": "교환", "Japanese": "交換"},
    "Action Count": {"Chinese": "行动次数", "Korean": "행동 횟수", "Japanese": "行動回数"},
    "Discarded": {"Chinese": "丢弃", "Korean": "버림", "Japanese": "捨てた"},
    "Fixed Ability": {"Chinese": "固有能力", "Korean": "고유 능력", "Japanese": "固有能力"},
    "Standby": {"Chinese": "待机", "Korean": "대기", "Japanese": "待機"},
    "Mana": {"Chinese": "AP", "Korean": "AP", "Japanese": "AP"},
    "stack": {"Chinese": "layer", "Korean": "layer", "Japanese": "layer"},
    "stacks": {"Chinese": "layers", "Korean": "layers", "Japanese": "layers"},
}

# Keys matching the mechanic prefixes that are not real mechanic terms.
_MECHANIC_IGNORED_KEYS = {
    "Battle/Keyword/Autodelete",
    "Battle/Keyword/CutScene",
    "Battle/Keyword/PlusSkillView",
    "Battle/Keyword/Quick_Desc_Casual",
}

# Strips sprite tags and stat placeholders from System/StatDesc values.
_STAT_DESC_CLEANUP = re.compile(r"<sprite[^>]*>|\{0\}%?")


_SUFFIX_CATEGORY: dict[str, str] = {
    "_PassiveName": "passives",
    "_SkinName": "other",
    "_Name": "names",
    "_name": "names",
}

# Key prefixes whose `_Name` values are descriptions, not actual names.
_IGNORED_NAME_KEY_PREFIXES = ("SkillExtended/",)


def _mechanic_english(key: str, english: str) -> str | None:
    """Return the cleaned mechanic term name if the key is a mechanic pattern.

    Patterns are `Battle/Keyword/*` (not `_Desc`), `Battle/SkillTooltip/*`, `System/StatDesc/*` and `_MECHANIC_EXACT_KEYS`.

    Args:
        key: Localization key.
        english: Raw English value.

    Returns:
        The English term name, or None if the key is not a mechanic pattern.
    """
    if key in _MECHANIC_IGNORED_KEYS:
        return None

    if key in _MECHANIC_EXACT_KEYS:
        return _MECHANIC_EXACT_KEYS[key]

    if any(key.startswith(p) for p in _MECHANIC_PREFIXES):
        if key.endswith("_Desc"):
            return None
        return english

    if key.startswith("System/StatDesc/"):
        return _STAT_DESC_CLEANUP.sub("", english).strip()

    return None


def _matches_prefix(key: str, prefix: str | list[str]) -> bool:
    """Check if a key starts with any of the given prefixes.

    Args:
        key: Localization key.
        prefix: One prefix or a list of them.

    Returns:
        Whether the key matches.
    """
    if isinstance(prefix, list):
        return any(key.startswith(p) for p in prefix)
    return key.startswith(prefix)


def build_glossary_from_base_game(
    base_strings: dict[str, LocString],
    term_categories: dict[str, str | list[str]],
    source_languages: list[str],
) -> dict[str, dict]:
    """Auto-build a glossary from the base game's name keys and mechanic keys.

    Args:
        base_strings: Base game `LocString` objects.
        term_categories: Category name -> key prefix mappings.
        source_languages: Source language names to include.

    Returns:
        Glossary dict.
    """
    glossary: dict[str, dict] = {"terms": {}}

    for key, loc_str in base_strings.items():
        is_name_key = any(key.endswith(suffix) for suffix in _NAME_KEY_SUFFIXES)

        english = loc_str.translations.get("English", "").strip().split("\n")[0].strip()
        if not english:
            continue

        mechanic_term = _mechanic_english(key, english)
        if mechanic_term is not None:
            category = "mechanics"
            english = mechanic_term
        elif not is_name_key:
            continue
        else:
            category = "other"
            for cat_name, prefix in term_categories.items():
                if _matches_prefix(key, prefix):
                    category = cat_name
                    break
            # Suffix and specific key patterns override the prefix-based category.
            if key.endswith("_PassiveName"):
                category = "passives"
            elif key.endswith("_SkinName"):
                category = "other"
            elif key.startswith("Character/AllyDoll_"):
                category = "other"

        if not english:
            continue

        source_mappings = {}
        for lang in source_languages:
            text = loc_str.translations.get(lang, "").strip().split("\n")[0].strip()
            if text:
                source_mappings[lang] = text

        now = datetime.now(UTC).isoformat()
        glossary["terms"][key] = {
            "english": english,
            "category": category,
            "key": key,
            "source_file": loc_str.source_file,
            "source_mappings": source_mappings,
            "created_at": now,
            "updated_at": now,
        }

    now = datetime.now(UTC).isoformat()
    for english, mappings in _MANUAL_MECHANIC_TERMS.items():
        manual_key = f"_manual/{english}"
        if manual_key not in glossary["terms"]:
            glossary["terms"][manual_key] = {
                "english": english,
                "category": "mechanics",
                "key": "",
                "source_file": "LangSystemDB.csv",
                "source_mappings": {lang: text for lang, text in mappings.items() if lang in source_languages},
                "created_at": now,
                "updated_at": now,
            }

    return glossary


def extract_name_key_suggestions(
    translated_keys: list[str],
    strings: dict[str, LocString],
    translations: dict[str, str],
    source_lang: str,
    existing_suggestions: list[dict],
    mod_glossary: dict,
    term_categories: dict[str, str | list[str]] | None = None,
) -> list[dict]:
    """Suggest glossary terms from just-translated name keys not already in the mod glossary or pending suggestions.

    Args:
        translated_keys: Keys that were just translated.
        strings: Key -> `LocString`.
        translations: Key -> English translation from the provider.
        source_lang: Source language name, e.g. `"Korean"`.
        existing_suggestions: Pending suggestions, for dedup.
        mod_glossary: The mod's current glossary.
        term_categories: Category name -> key prefix mappings, e.g. `{"characters": "Character/"}`.

    Returns:
        New suggestion dicts.
    """
    existing_english = {_TAG_PATTERN.sub("", s.get("english", "")).lower() for s in existing_suggestions}
    glossary_terms = {_TAG_PATTERN.sub("", info.get("english", t)).lower() for t, info in mod_glossary.get("terms", {}).items()}
    existing_sources: set[str] = set()
    for s in existing_suggestions:
        src = s.get("source", "").strip()
        if src:
            existing_sources.add(src)
    categories = term_categories or {}
    new_suggestions: list[dict] = []

    for key in translated_keys:
        # Check longest suffixes first so _PassiveName matches before _Name.
        matched_suffix = ""
        for suffix in _SUFFIX_CATEGORY:
            if key.endswith(suffix) and len(suffix) > len(matched_suffix):
                matched_suffix = suffix
        if not matched_suffix:
            continue

        if any(key.startswith(p) for p in _IGNORED_NAME_KEY_PREFIXES):
            continue

        english = translations.get(key, "").strip()
        if not english:
            continue

        # Skip if already known (case-insensitive, ignoring markup tags).
        stripped = _TAG_PATTERN.sub("", english).lower()
        if stripped in existing_english or stripped in glossary_terms:
            continue

        loc_str = strings.get(key)
        source_text = ""
        if loc_str:
            source_text = loc_str.translations.get(source_lang, "").strip()

        # Skip if the same source text was already suggested.
        if source_text and source_text in existing_sources:
            continue

        category = _SUFFIX_CATEGORY[matched_suffix]
        for cat_name, prefix in categories.items():
            if _matches_prefix(key, prefix):
                category = cat_name
                break

        new_suggestions.append(
            {
                "english": english,
                "source": source_text,
                "source_lang": source_lang,
                "category": category,
                "reason": "Auto-detected from name key after translation",
            }
        )
        existing_english.add(stripped)
        if source_text:
            existing_sources.add(source_text)

    return new_suggestions


# Categories whose terms are proper nouns and get title-cased.
_TITLE_CASE_CATEGORIES = {"characters", "names", "skills", "passives", "items", "buffs/debuffs"}

# Minor words kept lowercase in title case unless first.
_TITLE_CASE_MINOR_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "in", "on", "at", "to", "of", "by", "is"}


_TAG_PATTERN = re.compile(r"(<[^>]+>)")


def _title_case(text: str) -> str:
    """Title-case the text between markup tags like `<color=...>`, leaving the tags as-is.

    Args:
        text: Text to title-case.

    Returns:
        The title-cased text.
    """
    parts = _TAG_PATTERN.split(text)
    result = []
    first_word_seen = False
    for part in parts:
        if _TAG_PATTERN.fullmatch(part):
            result.append(part)
            continue
        words = part.split()
        cased = []
        for word in words:
            if not first_word_seen or word.lower() not in _TITLE_CASE_MINOR_WORDS:
                cased.append(word.capitalize())
            else:
                cased.append(word.lower())
            first_word_seen = True
        result.append(" ".join(cased))
    return "".join(result)


def suggest_glossary_edits(
    mod_glossary: dict,
    existing_suggestions: list[dict],
) -> list[dict]:
    """Suggest title-cased versions of existing glossary terms in name-related categories.

    Args:
        mod_glossary: The mod's current glossary.
        existing_suggestions: Pending suggestions, for dedup.

    Returns:
        Edit suggestion dicts, each with an `edit_of` field naming the original term.
    """
    existing_english = {s.get("english", "").lower() for s in existing_suggestions}
    terms = mod_glossary.get("terms", {})
    edits: list[dict] = []

    for term_key, info in terms.items():
        english = info.get("english", term_key)
        category = info.get("category", "")
        if category not in _TITLE_CASE_CATEGORIES:
            continue

        title_cased = _title_case(english)
        if title_cased == english:
            continue

        if title_cased.lower() in existing_english:
            continue

        mappings = info.get("source_mappings", {})
        source_lang = next(iter(mappings), "")
        source_text = mappings.get(source_lang, "") if source_lang else ""

        edits.append(
            {
                "english": title_cased,
                "source": source_text,
                "source_lang": source_lang,
                "category": category,
                "reason": f"Title case: '{english}' -> '{title_cased}'",
                "edit_of": term_key,
            }
        )
        existing_english.add(title_cased.lower())

    return edits


def load_glossary(path: Path) -> dict:
    """Load the glossary from a JSON file.

    Args:
        path: Glossary file, usually `glossary_path(game_id)`.

    Returns:
        Glossary dict, empty structure if the file doesn't exist.
    """
    if not path.exists():
        return {"terms": {}}

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_glossary(glossary: dict, path: Path) -> None:
    """Save the glossary to a JSON file.

    Args:
        glossary: Glossary dict.
        path: Target file, usually `glossary_path(game_id)`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    write_json(path, glossary)

    print(f"  Glossary saved to {path} ({len(glossary.get('terms', {}))} terms)")


def add_glossary_term(
    glossary: dict,
    english_term: str,
    source_mappings: dict[str, str] | None = None,
    category: str = "custom",
) -> dict:
    """Add or update a term in the glossary.

    Args:
        glossary: Glossary dict, modified in place.
        english_term: Canonical English term.
        source_mappings: Source language mappings.
        category: Term category, e.g. "characters" or "custom".

    Returns:
        The modified glossary.
    """
    if "terms" not in glossary:
        glossary["terms"] = {}

    now = datetime.now(UTC).isoformat()

    # Key by the first source text when available, else the English term.
    if source_mappings:
        term_key = next(iter(source_mappings.values()))
    else:
        term_key = english_term

    existing = glossary["terms"].get(term_key)
    created_at = existing.get("created_at", now) if existing else now

    glossary["terms"][term_key] = {
        "english": english_term,
        "category": category,
        "key": "",
        "source_file": "",
        "source_mappings": source_mappings or {},
        "created_at": created_at,
        "updated_at": now,
    }

    return glossary


def get_glossary_prompt(
    glossary: dict,
    allowed_categories: list[str] | None = None,
    source_lang: str | None = None,
    exclude_terms: set[str] | None = None,
    target_lang: str = "English",
) -> str:
    """Format the glossary as LLM prompt context.

    Into English it shows English terms with source mappings. Into another language the direction is reversed.

    Args:
        glossary: Glossary dict.
        allowed_categories: Categories to include, defaulting to `settings.glossary_categories`. An empty list disables filtering.
        source_lang: Only include mappings for this language, which shrinks the prompt.
        exclude_terms: English terms to skip.
        target_lang: Target language name.

    Returns:
        Prompt section, empty if no terms qualify.
    """
    if not glossary.get("terms"):
        return ""

    if allowed_categories is None:
        allowed_categories = settings.glossary_categories

    reverse = target_lang != "English"

    lines = [
        "## Game Terminology Glossary",
        "",
        f"Use these EXACT {target_lang} terms when translating. Do not paraphrase:",
        "",
    ]

    by_category: dict[str, list[tuple[str, dict]]] = {}
    for term_key, info in glossary["terms"].items():
        english_term = info.get("english", term_key)
        if exclude_terms and english_term in exclude_terms:
            continue
        cat = info.get("category", "other")
        if allowed_categories and cat not in allowed_categories:
            continue

        mappings = info.get("source_mappings", {})
        if reverse:
            # Only terms with a target language mapping are usable in reverse.
            if target_lang not in mappings:
                continue
        elif source_lang:
            if source_lang not in mappings:
                continue

        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((english_term, info))

    if not by_category:
        return ""

    for category, terms in sorted(by_category.items()):
        lines.append(f"### {category.title()}")
        for english_term, info in sorted(terms, key=lambda x: x[0]):
            mappings = info.get("source_mappings", {})
            if reverse:
                target_term = mappings.get(target_lang, english_term)
                lines.append(f"- **{target_term}** ← English: {english_term}")
            elif mappings:
                if source_lang and source_lang in mappings:
                    mapping_str = f"{source_lang}: {mappings[source_lang]}"
                else:
                    mapping_str = ", ".join(f"{lang}: {text}" for lang, text in mappings.items())
                lines.append(f"- **{english_term}** ← {mapping_str}")
            else:
                lines.append(f"- **{english_term}**")
        lines.append("")

    return "\n".join(lines)


def get_combined_glossary_prompt(
    base: dict,
    mod: dict,
    source_lang: str | None = None,
    target_lang: str = "English",
    allowed_categories: list[str] | None = None,
) -> str:
    """Build a glossary prompt from the base and mod glossaries.

    Base terms are filtered by category to control prompt size. Mod terms are user-curated so always included, and override base terms.

    Args:
        base: Base game glossary.
        mod: Mod glossary.
        source_lang: Only include mappings for this language.
        target_lang: Target language name.
        allowed_categories: Base categories to include, defaulting to `settings.glossary_categories`.

    Returns:
        Combined prompt section.
    """
    mod_term_keys = set(mod.get("terms", {}).keys())

    base_prompt = get_glossary_prompt(
        base,
        allowed_categories=allowed_categories if allowed_categories is not None else settings.glossary_categories,
        source_lang=source_lang,
        exclude_terms=mod_term_keys,
        target_lang=target_lang,
    )
    mod_prompt = get_glossary_prompt(mod, allowed_categories=[], source_lang=source_lang, target_lang=target_lang)

    if base_prompt and mod_prompt:
        # Drop the mod prompt's duplicate header.
        mod_body = mod_prompt.split("\n\n", 2)
        if len(mod_body) > 2:
            return base_prompt + "\n" + mod_body[2]
        return base_prompt + "\n" + mod_prompt
    return mod_prompt or base_prompt


def load_mod_glossary(mod_id: str, *, game_id: str) -> dict:
    """Load a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Glossary dict, empty structure if none exists.
    """
    mods_dir = mods_path(game_id)
    path = mods_dir / mod_id / "glossary.json"
    if not path.exists():
        return {"terms": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_mod_glossary(mod_id: str, glossary: dict, *, game_id: str) -> None:
    """Save a mod's glossary.

    Args:
        mod_id: Mod's Workshop id.
        glossary: Glossary dict.
        game_id: Game the mod belongs to.
    """
    mods_dir = mods_path(game_id)
    path = mods_dir / mod_id / "glossary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, glossary)


def merge_glossaries(base: dict, mod: dict) -> dict:
    """Merge base and mod glossaries, with mod terms overriding base on collision.

    Args:
        base: Base game glossary.
        mod: Mod glossary.

    Returns:
        Merged glossary.
    """
    merged_terms = {**base.get("terms", {}), **mod.get("terms", {})}
    return {"terms": merged_terms}


def print_glossary(glossary: dict) -> None:
    """Print the glossary in a human-readable format.

    Args:
        glossary: Glossary dict.
    """
    terms = glossary.get("terms", {})
    if not terms:
        print("Glossary is empty.")
        return

    by_category: dict[str, list[tuple[str, dict]]] = {}
    for term_key, info in terms.items():
        cat = info.get("category", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((term_key, info))

    for category, term_list in sorted(by_category.items()):
        print(f"\n=== {category.upper()} ({len(term_list)} terms) ===")
        for term_key, info in sorted(term_list, key=lambda x: x[0]):
            english = info.get("english", term_key)
            mappings = info.get("source_mappings", {})
            if mappings:
                first_mapping = next(iter(mappings.values()))
                print(f"  {english} ← {first_mapping}")
            else:
                print(f"  {english}")

    print(f"\nTotal: {len(terms)} terms")


def replace_whole_term(text: str, old_term: str, new_term: str) -> tuple[str, int]:
    """Replace `old_term` with `new_term` wherever it stands alone in `text`.

    A match must not touch a letter, digit or underscore, so `Nangao` is not replaced inside `Nangaoese`. Unlike a plain `\\b`, this also works
    for terms starting or ending with punctuation, such as `[Lord of Wind] Lidao`.

    Args:
        text: Text to search.
        old_term: Term to replace.
        new_term: Replacement, inserted literally.

    Returns:
        The new text and the replacement count.
    """
    pattern = re.compile(r"(?<!\w)" + re.escape(old_term) + r"(?!\w)")
    return pattern.subn(lambda _match: new_term, text)
