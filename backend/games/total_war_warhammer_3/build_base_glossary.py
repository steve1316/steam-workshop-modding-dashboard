"""Build the WH3 base-game terminology glossary from extracted vanilla loc files.

Reads the English per-table TSVs and the merged Chinese/Korean loc files, extracts stats, attributes, ui_terms and regions,
dedupes by English value, applies per-category exclusions, and writes a `{"terms": {...}}` glossary to the WH3 storage path.
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

from backend.data.glossary_manager import save_glossary
from backend.games.storage_paths import glossary_path

GAME_ID = "total_war_warhammer_3"

# Strips `[[...]]` markup tokens and `{{...}}` substitution tokens.
_MARKUP = re.compile(r"\[\[[^\]]*\]\]|\{\{[^}]*\}\}")

# Splits `Term: value` on an ASCII colon or a CJK fullwidth colon (U+FF1A). Chinese loc values use the fullwidth form.
_COLON = re.compile("[:" + chr(0xFF1A) + "]")

# Curated allowlist of system terms, matched case-insensitively against candidate labels.
UI_TERMS_ALLOWLIST: set[str] = {
    "cooldown",
    "income",
    "upkeep",
    "active time",
    "spell",
    "ability",
    "casualty replenishment rate",
    "maintenance cost",
    "public order",
    "growth",
    "corruption",
}

# Source files scanned for ui_terms. Effects values are `Term: value`, so they use before-colon labels.
_UI_TERM_SOURCES = (
    "random_localisation_strings__.loc.tsv",
    "unit_ability_source_types__.loc.tsv",
    "effects__.loc.tsv",
)

# English terms dropped per category: mostly unit-name attributes and niche stats.
_EXCLUDED_TERMS: dict[str, frozenset[str]] = {
    "attributes": frozenset(
        {
            "Ballistic Plating",
            "Boar Cavalry",
            "Bound Fire Daemon",
            "Goblin Infantry",
            "Gorger",
            "Kroxigor",
            "Moulder Monster",
            "Nasty Skulker",
            "Night Goblin Archer",
            "Orc Infantry",
            "Skink",
            "Slayer",
            "Spider",
            "Squig",
            "Squig Herd",
            "Tiger Warrior",
            "Troll",
            "Woodsman",
        }
    ),
    "stats": frozenset(
        {
            "Dealt Collision Knocked Back Threshold",
            "Dealt Collision Knocked Down Threshold",
            "Dealt Collision Knocked Flying Threshold",
            "Ship Health",
            "Ship Speed",
        }
    ),
}

# Attribute terms with this prefix are dropped (e.g. "Removes Fear").
_REMOVES_PREFIX = "Removes "


def _clean(text: str) -> str:
    """Return the clean term name: the part before `||`, markup stripped, whitespace collapsed.

    Args:
        text: Raw loc value.

    Returns:
        Cleaned term name.
    """
    name = text.split("||", 1)[0]
    name = _MARKUP.sub("", name)
    return " ".join(name.split()).strip()


def _term_before_colon(text: str) -> str:
    """Return the label before the first colon of a `Term: value` effect string.

    Markup is stripped first so a colon inside a tag does not split the label.

    Args:
        text: Raw loc value.

    Returns:
        Cleaned label.
    """
    stripped = _MARKUP.sub("", text.split("||", 1)[0])
    stripped = " ".join(stripped.split()).strip()
    return _COLON.split(stripped, 1)[0].strip()


def _is_excluded(english: str, category: str) -> bool:
    """Return True when an extracted term should be dropped from the glossary.

    Args:
        english: Cleaned English term.
        category: Term's category.

    Returns:
        True when excluded for the category or a `Removes ...` attribute.
    """
    if english in _EXCLUDED_TERMS.get(category, frozenset()):
        return True
    if category == "attributes" and english.startswith(_REMOVES_PREFIX):
        return True
    return False


def _parse_tsv(path: Path) -> dict[str, str]:
    """Parse a loc TSV into `key -> text`, skipping the two header lines.

    Args:
        path: `*.loc.tsv` file.

    Returns:
        Loc key to raw text, empty when the file is missing.
    """
    result: dict[str, str] = {}
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:  # column header: key\ttext\ttooltip
                continue
            line = line.rstrip("\n")
            if not line or line.startswith("#Loc"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            key = parts[0]
            if key:
                result[key] = parts[1]
    return result


# Hand-picked phrasings the vanilla files do not yield as clean terms. Added after extraction so a rebuild keeps them.
CURATED_TERMS: list[dict] = [
    # Reads like the base game's "Unlocks recruitment of ...".
    {"english": "Unlocks recruitment for", "category": "ui_terms", "source_mappings": {"Chinese": "招募许可"}},
]


def add_curated_terms(glossary: dict) -> dict:
    """Add `CURATED_TERMS` to a glossary, replacing any entry with the same English.

    Args:
        glossary: `{"terms": {english: {...}}}`, updated in place.

    Returns:
        The same glossary.
    """
    now = datetime.now(UTC).isoformat()
    for term in CURATED_TERMS:
        glossary["terms"][term["english"]] = {
            "english": term["english"],
            "category": term["category"],
            "key": "",
            "source_file": "curated",
            "source_mappings": dict(term["source_mappings"]),
            "created_at": now,
            "updated_at": now,
        }
    return glossary


def build_glossary(en_db_dir: Path, cn_file: Path, kr_file: Path) -> dict:
    """Build the base-game glossary dict from the vanilla loc files.

    Extracts in priority order [stats, attributes, ui_terms, regions], skipping empty and excluded values.
    Dedupes case-insensitively by English so the first occurrence wins, then adds `CURATED_TERMS`.

    Args:
        en_db_dir: Directory of English per-table `*.loc.tsv` files.
        cn_file: Merged Chinese `localisation__.loc.tsv`.
        kr_file: Merged Korean `localisation__.loc.tsv`.

    Returns:
        `{"terms": {english: {...}}}`.
    """
    cn = _parse_tsv(cn_file)
    kr = _parse_tsv(kr_file)
    now = datetime.now(UTC).isoformat()
    terms: dict[str, dict] = {}
    seen: set[str] = set()

    def add(english: str, category: str, key: str, source_file: str, colon: bool) -> None:
        if not english or _is_excluded(english, category):
            return
        norm = english.lower()
        if norm in seen:
            return
        seen.add(norm)
        mappings: dict[str, str] = {}
        cn_raw = cn.get(key, "")
        kr_raw = kr.get(key, "")
        cn_val = _term_before_colon(cn_raw) if colon else _clean(cn_raw)
        kr_val = _term_before_colon(kr_raw) if colon else _clean(kr_raw)
        if cn_val:
            mappings["Chinese"] = cn_val
        if kr_val:
            mappings["Korean"] = kr_val
        terms[english] = {
            "english": english,
            "category": category,
            "key": key,
            "source_file": source_file,
            "source_mappings": mappings,
            "created_at": now,
            "updated_at": now,
        }

    # stats: clean onscreen names only
    for key, text in _parse_tsv(en_db_dir / "unit_stat_localisations__.loc.tsv").items():
        if "_onscreen_name_" not in key:
            continue
        add(_clean(text), "stats", key, "unit_stat_localisations__.loc.tsv", colon=False)

    # attributes: name before `||`
    for key, text in _parse_tsv(en_db_dir / "unit_attributes__.loc.tsv").items():
        add(_clean(text), "attributes", key, "unit_attributes__.loc.tsv", colon=False)

    # ui_terms: allowlist across multiple files
    for fname in _UI_TERM_SOURCES:
        is_effects = fname == "effects__.loc.tsv"
        for key, text in _parse_tsv(en_db_dir / fname).items():
            candidate = _term_before_colon(text) if is_effects else _clean(text)
            if candidate.lower() in UI_TERMS_ALLOWLIST:
                add(candidate, "ui_terms", key, fname, colon=is_effects)

    # regions: canonical onscreen names only
    for key, text in _parse_tsv(en_db_dir / "regions__.loc.tsv").items():
        if not key.startswith("regions_onscreen_"):
            continue
        add(_clean(text), "regions", key, "regions__.loc.tsv", colon=False)

    return add_curated_terms({"terms": terms})


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint: build the glossary from the vanilla folders and write it to storage.

    Args:
        argv: Argument list, defaults to `sys.argv`.
    """
    parser = argparse.ArgumentParser(description="Build the WH3 base-game terminology glossary.")
    parser.add_argument("--vanilla-root", type=Path, default=Path("."), help="Folder containing vanilla_text_en/cn/kr.")
    parser.add_argument("--out", type=Path, default=None, help="Output glossary.json path (defaults to WH3 storage).")
    args = parser.parse_args(argv)

    en_db = args.vanilla_root / "vanilla_text_en" / "db"
    cn_file = args.vanilla_root / "vanilla_text_cn" / "text" / "localisation__.loc.tsv"
    kr_file = args.vanilla_root / "vanilla_text_kr" / "text" / "localisation__.loc.tsv"

    glossary = build_glossary(en_db, cn_file, kr_file)
    out = args.out if args.out is not None else glossary_path(GAME_ID)
    save_glossary(glossary, out)
    print(f"Wrote {len(glossary['terms'])} terms to {out}")


if __name__ == "__main__":
    main()
