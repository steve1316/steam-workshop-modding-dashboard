"""
Glossary manager for consistent English terminology.

Builds and maintains a glossary of official English game terms extracted
from the base game's localization files. The glossary maps source language
terms to their canonical English translations. Supports per-mod glossaries
that overlay the base game glossary.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend import config
from backend.games.storage_paths import glossary_path, mods_path
from backend.models import LocString
from backend.core.json_store import write_json


# Common game terms to auto-extract from the base game.
_NAME_KEY_SUFFIXES = ("_Name", "_name", "_PassiveName", "_SkinName")

# Key patterns that yield mechanic terms. Each entry is a prefix; the
# English value of matching keys is used as the term name.
_MECHANIC_PREFIXES = ("Battle/Keyword/", "Battle/SkillTooltip/")

# Exact keys that map to a specific mechanic term.
_MECHANIC_EXACT_KEYS: dict[str, str] = {
    "System/Debuff": "Debuff",
    "UI/CharStat/PartyStat_MP": "Mana",
    "UI/Battle/Buff/Barrier": "Barrier",
}

# Manual mechanic terms that appear within other strings but have no
# dedicated key. Each entry maps the English term to its known source
# language translations.
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

# Mechanic-pattern keys to skip (not actual mechanic terms).
_MECHANIC_IGNORED_KEYS = {
    "Battle/Keyword/Autodelete",
    "Battle/Keyword/CutScene",
    "Battle/Keyword/PlusSkillView",
    "Battle/Keyword/Quick_Desc_Casual",
}

# Regex to strip sprite tags and stat placeholders from System/StatDesc values.
_STAT_DESC_CLEANUP = re.compile(r"<sprite[^>]*>|\{0\}%?")


# Suffix-to-category mapping for mod name-key auto-detection.
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

    Mechanic patterns:
    - `Battle/Keyword/xxx` (excluding `_Desc` suffixes)
    - `Battle/SkillTooltip/xxx`
    - `System/StatDesc/xxx` (cleaned of sprite tags and placeholders)
    - Exact keys in `_MECHANIC_EXACT_KEYS`

    Args:
        key: The localization key to classify.
        english: The raw English value from the localization data.

    Returns:
        The cleaned English term name, or None if the key is not a
        mechanic pattern.
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
    """Check if a key starts with any of the given prefix(es).

    Args:
        key: The localization key to test.
        prefix: A single prefix string or a list of prefix strings.

    Returns:
        True if the key starts with any of the given prefixes.
    """
    if isinstance(prefix, list):
        return any(key.startswith(p) for p in prefix)
    return key.startswith(prefix)


def build_glossary_from_base_game(
    base_strings: dict[str, LocString],
    term_categories: dict[str, str | list[str]],
    source_languages: list[str],
) -> dict[str, dict]:
    """
    Auto-build a glossary from the base game's localization data.

    Extracts name entries (keys ending in _Name, _name, _PassiveName, or
    _SkinName) and mechanic terms from keyword keys, skill tooltip keys,
    stat description keys, and specific exact keys.

    Args:
        base_strings: Dictionary of base game LocString objects.
        term_categories: Category name -> key prefix mappings.
        source_languages: List of source language names to include.

    Returns:
        Glossary dictionary.
    """
    glossary: dict[str, dict] = {"terms": {}}

    for key, loc_str in base_strings.items():
        is_name_key = any(key.endswith(suffix) for suffix in _NAME_KEY_SUFFIXES)

        english = loc_str.translations.get("English", "").strip().split("\n")[0].strip()
        if not english:
            continue

        # Determine the category and clean up the English term.
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
            # Suffix and specific key patterns override prefix-based category.
            if key.endswith("_PassiveName"):
                category = "passives"
            elif key.endswith("_SkinName"):
                category = "other"
            elif key.startswith("Character/AllyDoll_"):
                category = "other"

        if not english:
            continue

        # Build source language mappings.
        source_mappings = {}
        for lang in source_languages:
            text = loc_str.translations.get(lang, "").strip().split("\n")[0].strip()
            if text:
                source_mappings[lang] = text

        now = datetime.now(timezone.utc).isoformat()
        glossary["terms"][key] = {
            "english": english,
            "category": category,
            "key": key,
            "source_file": loc_str.source_file,
            "source_mappings": source_mappings,
            "created_at": now,
            "updated_at": now,
        }

    # Add manual mechanic terms that have no dedicated key.
    now = datetime.now(timezone.utc).isoformat()
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
    """Extract glossary suggestions from translated name keys.

    Scans the translated keys for entries ending in name suffixes
    (`_Name`, `_name`, `_PassiveName`, `_SkinName`). Any such entry whose
    English translation is not already in the mod glossary or pending
    suggestions is returned as a new suggestion marked as auto-detected.

    Args:
        translated_keys: Keys that were just translated.
        strings: Full strings dict mapping key -> LocString.
        translations: Key -> English translation mapping from the provider.
        source_lang: Source language name (e.g. `"Korean"`).
        existing_suggestions: Already-pending suggestion dicts for dedup.
        mod_glossary: The mod's current glossary dict.
        term_categories: Optional category name -> key prefix mappings for
            categorising suggestions (e.g. `{"characters": "Character/"}`).

    Returns:
        List of new suggestion dicts ready to be stored.
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

        # Skip prefixes whose _Name fields hold descriptions, not names.
        if any(key.startswith(p) for p in _IGNORED_NAME_KEY_PREFIXES):
            continue

        english = translations.get(key, "").strip()
        if not english:
            continue

        # Skip if already known (case-insensitive, ignoring markup tags).
        stripped = _TAG_PATTERN.sub("", english).lower()
        if stripped in existing_english or stripped in glossary_terms:
            continue

        # Determine source text.
        loc_str = strings.get(key)
        source_text = ""
        if loc_str:
            source_text = loc_str.translations.get(source_lang, "").strip()

        # Skip if the same source text was already suggested.
        if source_text and source_text in existing_sources:
            continue

        # Determine category from key prefix or suffix default.
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


# Categories whose terms should be title-cased (proper nouns / names).
_TITLE_CASE_CATEGORIES = {"characters", "names", "skills", "passives", "items", "buffs/debuffs"}

# Lowercase words that should stay lowercase in title case (articles, etc.).
_TITLE_CASE_MINOR_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "in", "on", "at", "to", "of", "by", "is"}


_TAG_PATTERN = re.compile(r"(<[^>]+>)")


def _title_case(text: str) -> str:
    """Convert text to title case, preserving markup tags like `<color=...>`.

    Tags are kept as-is. Only the text segments between tags are title-cased,
    with minor words kept lowercase unless they are the first visible word.

    Args:
        text: The input text to title-case.

    Returns:
        The title-cased text with tags preserved.
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
    """Suggest edits to existing glossary terms, such as title-casing names.

    Scans glossary terms in name-related categories and suggests title-cased
    versions for terms that aren't already title-cased.

    Args:
        mod_glossary: The mod's current glossary dict.
        existing_suggestions: Already-pending suggestion dicts for dedup.

    Returns:
        List of edit suggestion dicts with an `edit_of` field referencing
        the original term.
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


def load_glossary(path: Optional[Path] = None) -> dict:
    """
    Load the glossary from a JSON file.

    Args:
        path: Path to the glossary file. Defaults to storage/glossary.json.

    Returns:
        Glossary dictionary, or empty structure if file doesn't exist.
    """
    if path is None:
        path = glossary_path("chrono_ark")

    if not path.exists():
        return {"terms": {}}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_glossary(glossary: dict, path: Optional[Path] = None) -> None:
    """
    Save the glossary to a JSON file.

    Args:
        glossary: The glossary dictionary to save.
        path: Path to save to. Defaults to storage/glossary.json.
    """
    if path is None:
        path = glossary_path("chrono_ark")

    path.parent.mkdir(parents=True, exist_ok=True)

    write_json(path, glossary)

    print(f"  Glossary saved to {path} ({len(glossary.get('terms', {}))} terms)")


def add_glossary_term(
    glossary: dict,
    english_term: str,
    source_mappings: Optional[dict[str, str]] = None,
    category: str = "custom",
) -> dict:
    """
    Add or update a term in the glossary.

    Args:
        glossary: The glossary dictionary to modify.
        english_term: The canonical English term.
        source_mappings: Optional source language mappings.
        category: Term category (e.g., "characters", "buffs/debuffs", "custom").

    Returns:
        The modified glossary dictionary.
    """
    if "terms" not in glossary:
        glossary["terms"] = {}

    now = datetime.now(timezone.utc).isoformat()

    # Use the first source text as the unique key when available,
    # otherwise fall back to the English term.
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
    """
    Format the glossary as context for an LLM translation prompt.

    When translating into English (default), shows English terms bold with
    source language mappings. When translating from English into a CJK
    language, reverses the direction: shows the target language term bold
    with the English source mapping.

    Args:
        glossary: The glossary dictionary.
        allowed_categories: If provided, only include terms from these categories.
            Defaults to config.GLOSSARY_CATEGORIES. Pass an empty list to
            disable category filtering entirely.
        source_lang: If provided, only include mappings for this language.
            This significantly reduces prompt size.
        exclude_terms: If provided, skip any term whose key is in this set.
        target_lang: The language being translated into. Defaults to `"English"`.

    Returns:
        Formatted string suitable for use as LLM system prompt context.
    """
    if not glossary.get("terms"):
        return ""

    if allowed_categories is None:
        allowed_categories = config.GLOSSARY_CATEGORIES

    reverse = target_lang != "English"

    lines = [
        "## Game Terminology Glossary",
        "",
        f"Use these EXACT {target_lang} terms when translating. Do not paraphrase:",
        "",
    ]

    # Group by category, filtering to allowed categories.
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
            # When translating English→CJK, only include terms that have
            # a mapping for the target language.
            if target_lang not in mappings:
                continue
        elif source_lang:
            # Only include terms that have a mapping for the source language.
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
                # Show target-language term bold, English as source.
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
    """
    Build a glossary prompt from base and mod glossaries.

    Base glossary terms are filtered by config.GLOSSARY_CATEGORIES to control
    prompt size. Mod glossary terms are always included (user-curated).
    Mod terms that override base terms appear only once (unfiltered).

    Args:
        base: The base game glossary.
        mod: The mod-specific glossary.
        source_lang: If provided, only include mappings for this language.
        target_lang: The language being translated into. Defaults to `"English"`.
        allowed_categories: Base-glossary categories to include. Defaults to config.GLOSSARY_CATEGORIES when None.

    Returns:
        Combined formatted glossary prompt string.
    """
    mod_term_keys = set(mod.get("terms", {}).keys())

    base_prompt = get_glossary_prompt(
        base,
        allowed_categories=allowed_categories if allowed_categories is not None else config.GLOSSARY_CATEGORIES,
        source_lang=source_lang,
        exclude_terms=mod_term_keys,
        target_lang=target_lang,
    )
    # Pass empty list to disable category filtering for mod terms.
    mod_prompt = get_glossary_prompt(mod, allowed_categories=[], source_lang=source_lang, target_lang=target_lang)

    if base_prompt and mod_prompt:
        # Strip the duplicate header from the mod prompt and append its terms.
        mod_body = mod_prompt.split("\n\n", 2)
        if len(mod_body) > 2:
            return base_prompt + "\n" + mod_body[2]
        return base_prompt + "\n" + mod_prompt
    return mod_prompt or base_prompt


def load_mod_glossary(mod_id: str, storage_path: Optional[Path] = None) -> dict:
    """
    Load a mod-specific glossary.

    Args:
        mod_id: The mod's Workshop ID.
        storage_path: Base storage path. Defaults to config.STORAGE_PATH.

    Returns:
        Glossary dictionary, or empty structure if none exists.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "glossary.json"
    if not path.exists():
        return {"terms": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_mod_glossary(mod_id: str, glossary: dict, storage_path: Optional[Path] = None) -> None:
    """
    Save a mod-specific glossary.

    Args:
        mod_id: The mod's Workshop ID.
        glossary: The glossary dictionary to save.
        storage_path: Base storage path. Defaults to config.STORAGE_PATH.
    """
    mods_dir = (storage_path / "mods") if storage_path else mods_path("chrono_ark")
    path = mods_dir / mod_id / "glossary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, glossary)


def merge_glossaries(base: dict, mod: dict) -> dict:
    """
    Merge base game and mod glossaries. Mod terms override base on collision.

    Args:
        base: The base game glossary.
        mod: The mod-specific glossary.

    Returns:
        Merged glossary dictionary.
    """
    merged_terms = {**base.get("terms", {}), **mod.get("terms", {})}
    return {"terms": merged_terms}


def print_glossary(glossary: dict) -> None:
    """
    Print the glossary in a human-readable format.

    Args:
        glossary: The glossary dictionary to display.
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

    A match must not touch a letter, digit or underscore on either side, so `Nangao` is not replaced inside `Nangaoese`. Unlike a plain `\\b` match, this
    also works for terms that start or end with punctuation, such as `[Lord of Wind] Lidao`.

    Args:
        text: The text to search.
        old_term: The term to replace.
        new_term: The replacement, inserted literally.

    Returns:
        The new text and the number of replacements made.
    """
    pattern = re.compile(r"(?<!\w)" + re.escape(old_term) + r"(?!\w)")
    return pattern.subn(lambda _match: new_term, text)
