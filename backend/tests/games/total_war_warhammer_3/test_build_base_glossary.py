"""Tests for the WH3 base-game glossary build script."""

from pathlib import Path

from backend.games.total_war_warhammer_3.translation import base_glossary as bbg


def _write_tsv(path: Path, rows: list[tuple[str, str]]) -> None:
    """Write a loc TSV with the standard two header lines plus key/text rows."""
    lines = ["key\ttext\ttooltip", "#Loc;1;text/db/x.loc\t\t"]
    lines += [f"{k}\t{t}\tfalse" for k, t in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_clean_strips_markup_and_splits_name():
    assert bbg._clean("[[img:ui/x.png]][[/img]] Armour") == "Armour"
    assert bbg._clean("Always Flying||This unit is always flying.") == "Always Flying"
    assert bbg._clean("[[col:white]]Bound[[/col]] {{tr:morale}}") == "Bound"


def test_term_before_colon_takes_label():
    assert bbg._term_before_colon("Casualty replenishment rate: %+n% after sacking") == "Casualty replenishment rate"
    assert bbg._term_before_colon("Maintenance cost: [[col:red]]%n[[/col]]") == "Maintenance cost"
    # Chinese loc values use a CJK fullwidth colon (U+FF1A), which must also split.
    assert bbg._term_before_colon("Growth" + chr(0xFF1A) + "%+n") == "Growth"


def test_parse_tsv_skips_headers_and_blank_text(tmp_path: Path):
    p = tmp_path / "x.loc.tsv"
    _write_tsv(p, [("a", "Alpha"), ("b", ""), ("c", "Gamma")])
    parsed = bbg._parse_tsv(p)
    assert parsed == {"a": "Alpha", "b": "", "c": "Gamma"}
    assert "key" not in parsed  # header line skipped


def _make_vanilla(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a minimal en-db dir plus merged cn/kr files; return (en_db, cn_file, kr_file)."""
    en_db = tmp_path / "en" / "db"
    en_db.mkdir(parents=True)
    _write_tsv(
        en_db / "unit_stat_localisations__.loc.tsv",
        [
            ("unit_stat_localisations_onscreen_name_stat_armour", "[[img:x.png]][[/img]] Armour"),
            ("unit_stat_localisations_onscreen_name_scalar_ap_dmg", "Armour-Piercing Explosive Damage"),
            ("unit_stat_localisations_onscreen_name_scalar_ap_dmg2", "Armour-piercing explosive damage"),
            ("unit_stat_localisations_tooltip_armour", "How resistant a unit is."),
        ],
    )
    _write_tsv(
        en_db / "unit_attributes__.loc.tsv",
        [("unit_attributes_bullet_text_always_flying", "Always Flying||This unit is always flying.")],
    )
    _write_tsv(en_db / "random_localisation_strings__.loc.tsv", [("random_localisation_strings_string_cooldown", "Cooldown")])
    _write_tsv(en_db / "unit_ability_source_types__.loc.tsv", [("unit_ability_source_types_name_spell", "Spell")])
    _write_tsv(
        en_db / "effects__.loc.tsv",
        [
            ("effects_description_building_upkeep", "Maintenance cost: [[col:red]]%n[[/col]]"),
            ("effects_description_random_flavor", "Some long flavor text that is not a term"),
        ],
    )
    _write_tsv(
        en_db / "regions__.loc.tsv",
        [
            ("regions_onscreen_wh3_region_black_pit", "The Black Pit"),
            ("regions_battle_name_wh3_region_black_pit", "Battle of The Black Pit"),
        ],
    )

    cn = tmp_path / "cn.loc.tsv"
    _write_tsv(
        cn,
        [
            ("unit_stat_localisations_onscreen_name_stat_armour", "[[img:x.png]][[/img]] 护甲"),
            ("unit_attributes_bullet_text_always_flying", "永远飞行||此部队会永远飞行"),
            ("random_localisation_strings_string_cooldown", "冷却"),
            ("unit_ability_source_types_name_spell", "法术"),
            ("effects_description_building_upkeep", "维护费用: [[col:red]]%n[[/col]]"),
            ("regions_onscreen_wh3_region_black_pit", "黑暗深渊"),
        ],
    )
    kr = tmp_path / "kr.loc.tsv"
    _write_tsv(kr, [("unit_stat_localisations_onscreen_name_stat_armour", "방어구")])
    return en_db, cn, kr


def test_build_glossary_extracts_and_dedupes(tmp_path: Path):
    en_db, cn, kr = _make_vanilla(tmp_path)
    glossary = bbg.build_glossary(en_db, cn, kr)
    terms = glossary["terms"]

    # stats: onscreen names only; tooltip key excluded.
    assert terms["Armour"]["category"] == "stats"
    assert terms["Armour"]["source_mappings"] == {"Chinese": "护甲", "Korean": "방어구"}
    assert "How resistant a unit is." not in terms  # tooltip key skipped

    # case-insensitive dedupe keeps the first (Title-Case) variant.
    assert "Armour-Piercing Explosive Damage" in terms
    assert "Armour-piercing explosive damage" not in terms

    # attributes: name only, no description retained.
    assert terms["Always Flying"]["category"] == "attributes"
    assert terms["Always Flying"]["source_mappings"]["Chinese"] == "永远飞行"

    # ui_terms allowlist across files, incl. effects before-colon.
    assert terms["Cooldown"]["category"] == "ui_terms"
    assert terms["Spell"]["category"] == "ui_terms"
    assert terms["Maintenance cost"]["category"] == "ui_terms"
    assert terms["Maintenance cost"]["source_mappings"]["Chinese"] == "维护费用"
    assert "Some long flavor text that is not a term" not in terms  # not in allowlist

    # regions: onscreen only; battle_name variant excluded.
    assert terms["The Black Pit"]["category"] == "regions"
    assert "Battle of The Black Pit" not in terms


def test_main_writes_glossary_to_out_path(tmp_path: Path):
    import json
    import shutil

    # `_make_vanilla` returns a flat layout; `main` expects the nested vanilla_text_* layout,
    # so recreate that layout under a single root.
    en_db, cn, kr = _make_vanilla(tmp_path)
    root = tmp_path / "root"
    shutil.copytree(en_db, root / "vanilla_text_en" / "db")
    (root / "vanilla_text_cn" / "text").mkdir(parents=True)
    shutil.copy(cn, root / "vanilla_text_cn" / "text" / "localisation__.loc.tsv")
    (root / "vanilla_text_kr" / "text").mkdir(parents=True)
    shutil.copy(kr, root / "vanilla_text_kr" / "text" / "localisation__.loc.tsv")

    out = tmp_path / "out_glossary.json"
    bbg.main(["--vanilla-root", str(root), "--out", str(out)])

    data = json.loads(out.read_text(encoding="utf-8"))
    assert "Armour" in data["terms"]
    assert data["terms"]["Armour"]["category"] == "stats"


def test_build_glossary_applies_exclusions(tmp_path: Path):
    en_db = tmp_path / "en" / "db"
    en_db.mkdir(parents=True)
    _write_tsv(
        en_db / "unit_attributes__.loc.tsv",
        [
            ("unit_attributes_bullet_text_troll", "Troll||Counts as a Troll."),
            ("unit_attributes_bullet_text_removes_fear", "Removes Fear||No longer causes fear."),
            ("unit_attributes_bullet_text_strider", "Strider||Ignores terrain penalties."),
        ],
    )
    _write_tsv(
        en_db / "unit_stat_localisations__.loc.tsv",
        [
            ("unit_stat_localisations_onscreen_name_stat_ship_health", "Ship Health"),
            ("unit_stat_localisations_onscreen_name_stat_armour", "Armour"),
        ],
    )
    cn = tmp_path / "cn.loc.tsv"
    _write_tsv(cn, [])
    kr = tmp_path / "kr.loc.tsv"
    _write_tsv(kr, [])

    terms = bbg.build_glossary(en_db, cn, kr)["terms"]
    assert "Troll" not in terms  # excluded unit-name attribute
    assert "Removes Fear" not in terms  # Removes-prefixed attribute dropped
    assert "Ship Health" not in terms  # excluded stat
    assert "Strider" in terms  # non-excluded attribute kept
    assert "Armour" in terms  # non-excluded stat kept


def test_build_glossary_splits_fullwidth_colon_in_cn_mapping(tmp_path: Path):
    en_db = tmp_path / "en" / "db"
    en_db.mkdir(parents=True)
    _write_tsv(en_db / "effects__.loc.tsv", [("effects_description_corruption", "Corruption: %+n")])

    cn = tmp_path / "cn.loc.tsv"
    # Chinese value uses a fullwidth colon: "腐蚀：%+n" -> mapping should be just "腐蚀".
    _write_tsv(cn, [("effects_description_corruption", "腐蚀" + chr(0xFF1A) + "%+n")])
    kr = tmp_path / "kr.loc.tsv"
    _write_tsv(kr, [])

    terms = bbg.build_glossary(en_db, cn, kr)["terms"]
    assert terms["Corruption"]["category"] == "ui_terms"
    assert terms["Corruption"]["source_mappings"]["Chinese"] == "腐蚀"


def test_build_glossary_includes_curated_terms(tmp_path: Path):
    """Hand-picked phrasings are added after extraction, so a rebuild keeps them."""
    glossary = bbg.build_glossary(*_make_vanilla(tmp_path))
    term = glossary["terms"]["Unlocks recruitment for"]
    assert term["category"] == "ui_terms"
    assert term["source_mappings"] == {"Chinese": "招募许可"}


def test_curated_terms_reach_the_prompt_glossary():
    """Curated terms use a category the WH3 prompt includes, so Claude sees them."""
    from backend.data.glossary_manager import get_glossary_prompt
    from backend.games.total_war_warhammer_3.translation.context import BASE_GLOSSARY_PROMPT_CATEGORIES

    prompt = get_glossary_prompt(bbg.add_curated_terms({"terms": {}}), allowed_categories=BASE_GLOSSARY_PROMPT_CATEGORIES, source_lang="Chinese")
    assert "Unlocks recruitment for" in prompt
    assert "招募许可" in prompt
