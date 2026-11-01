from backend.data.glossary_manager import (
    add_glossary_term,
    build_glossary_from_base_game,
    get_combined_glossary_prompt,
    get_glossary_prompt,
    load_glossary,
    load_mod_glossary,
    merge_glossaries,
    save_glossary,
    save_mod_glossary,
)


def _find_by_english(terms: dict, english: str) -> dict:
    """Find a glossary entry by its English text field, failing the test when it is missing."""
    entry = next((info for info in terms.values() if info.get("english") == english), None)
    assert entry is not None, f"no glossary entry for {english!r}"
    return entry


def _has_english(terms: dict, english: str) -> bool:
    """Check if a glossary entry with the given English text exists."""
    return any(info.get("english") == english for info in terms.values())


def test_build_glossary_extracts_name_keys(sample_base_strings, glossary_categories):
    glossary = build_glossary_from_base_game(
        sample_base_strings,
        glossary_categories,
        ["Korean", "Chinese"],
    )
    terms = glossary["terms"]
    assert _has_english(terms, "Armor Increased")
    assert _has_english(terms, "Fire Bolt")
    assert _has_english(terms, "Lucy")
    assert _has_english(terms, "Heal")
    # Description keys should NOT be extracted.
    assert not _has_english(terms, "Defense is increased.")
    # Source file should be stored from the LocString.
    assert _find_by_english(terms, "Armor Increased")["source_file"] == "LangDataDB.csv"
    assert _find_by_english(terms, "Lucy")["source_file"] == "LangDataDB.csv"
    # SkillExtended/ keys should be categorized as skills.
    assert _find_by_english(terms, "Heal")["category"] == "skills"
    # _PassiveName suffix overrides Character/ prefix to passives.
    assert _find_by_english(terms, "Lucy's Blessing")["category"] == "passives"


def test_build_glossary_extracts_mechanic_keys(sample_base_strings, glossary_categories):
    glossary = build_glossary_from_base_game(
        sample_base_strings,
        glossary_categories,
        ["Korean", "Chinese"],
    )
    terms = glossary["terms"]
    # Battle/Keyword/ entries (without _Desc) are mechanics.
    assert _has_english(terms, "Innate")
    assert _find_by_english(terms, "Innate")["category"] == "mechanics"
    # _Desc keys should NOT be extracted.
    assert not _has_english(terms, "This skill is always in your hand.")
    # Battle/SkillTooltip/ entries are mechanics.
    assert _has_english(terms, "Accuracy")
    assert _find_by_english(terms, "Accuracy")["category"] == "mechanics"
    # Exact key System/Debuff maps to "Debuff".
    assert _has_english(terms, "Debuff")
    assert _find_by_english(terms, "Debuff")["category"] == "mechanics"
    assert _find_by_english(terms, "Debuff")["source_file"] == "LangSystemDB.csv"
    # System/StatDesc/ values are cleaned of sprites and placeholders.
    assert _has_english(terms, "Critical Hit Chance")
    assert _find_by_english(terms, "Critical Hit Chance")["category"] == "mechanics"


def test_build_glossary_sets_timestamps(sample_base_strings, glossary_categories):
    glossary = build_glossary_from_base_game(
        sample_base_strings,
        glossary_categories,
        ["Korean", "Chinese"],
    )
    for term, info in glossary["terms"].items():
        assert "created_at" in info, f"Missing created_at on {term}"
        assert "updated_at" in info, f"Missing updated_at on {term}"
        assert info["created_at"] is not None
        assert info["updated_at"] is not None


def test_save_and_load_glossary(tmp_storage):
    glossary = {"terms": {"Test": {"category": "custom", "key": "", "source_mappings": {}}}}
    path = tmp_storage / "glossary.json"
    save_glossary(glossary, path)
    loaded = load_glossary(path)
    assert loaded["terms"]["Test"]["category"] == "custom"


def test_add_glossary_term():
    glossary = {"terms": {}}
    add_glossary_term(glossary, "Fire Bolt", {"Korean": "화염구"}, category="skills")
    # Term is keyed by source text, not English.
    assert "화염구" in glossary["terms"]
    entry = glossary["terms"]["화염구"]
    assert entry["english"] == "Fire Bolt"
    assert entry["source_mappings"]["Korean"] == "화염구"
    assert entry["created_at"] is not None
    assert entry["updated_at"] is not None


def test_add_glossary_term_preserves_created_at():
    glossary = {"terms": {}}
    add_glossary_term(glossary, "Fire Bolt", {"Korean": "화염구"}, category="skills")
    original_created = glossary["terms"]["화염구"]["created_at"]
    add_glossary_term(glossary, "Fire Bolt", {"Korean": "화염구", "Chinese": "火球术"}, category="skills")
    assert glossary["terms"]["화염구"]["created_at"] == original_created


def test_glossary_prompt_format():
    glossary = {
        "terms": {
            "Fire Bolt": {"category": "skills", "key": "", "source_mappings": {"Korean": "화염구"}},
            "Armor": {"category": "mechanics", "key": "", "source_mappings": {}},
        }
    }
    prompt = get_glossary_prompt(glossary, allowed_categories=["skills", "mechanics"])
    assert "**Fire Bolt**" in prompt
    assert "**Armor**" in prompt
    assert "Korean: 화염구" in prompt


def test_load_mod_glossary_empty(tmp_storage):
    result = load_mod_glossary("12345", tmp_storage)
    assert result == {"terms": {}}


def test_save_and_load_mod_glossary(tmp_storage):
    glossary = {"terms": {"Dark Mage": {"category": "characters", "key": "", "source_mappings": {"Chinese": "黑魔法师"}}}}
    save_mod_glossary("12345", glossary, tmp_storage)
    loaded = load_mod_glossary("12345", tmp_storage)
    assert "Dark Mage" in loaded["terms"]


def test_merge_glossaries_mod_overrides_base():
    base = {"terms": {"Fire": {"category": "mechanics", "key": "", "source_mappings": {}}}}
    mod = {"terms": {"Fire": {"category": "skills", "key": "Skill/Fire_Name", "source_mappings": {"Korean": "불"}}}}
    merged = merge_glossaries(base, mod)
    assert merged["terms"]["Fire"]["category"] == "skills"
    assert merged["terms"]["Fire"]["source_mappings"]["Korean"] == "불"


def test_merge_glossaries_combines_both():
    base = {"terms": {"Armor": {"category": "mechanics", "key": "", "source_mappings": {}}}}
    mod = {"terms": {"Dark Mage": {"category": "characters", "key": "", "source_mappings": {}}}}
    merged = merge_glossaries(base, mod)
    assert "Armor" in merged["terms"]
    assert "Dark Mage" in merged["terms"]


def test_delete_mod_glossary_term(tmp_storage):
    glossary = {
        "terms": {
            "A": {"category": "c", "key": "", "source_mappings": {}},
            "B": {"category": "c", "key": "", "source_mappings": {}},
        }
    }
    save_mod_glossary("12345", glossary, tmp_storage)
    loaded = load_mod_glossary("12345", tmp_storage)
    del loaded["terms"]["A"]
    save_mod_glossary("12345", loaded, tmp_storage)
    reloaded = load_mod_glossary("12345", tmp_storage)
    assert "A" not in reloaded["terms"]
    assert "B" in reloaded["terms"]


def test_combined_glossary_prompt_includes_mod_terms_from_all_categories():
    """Mod glossary terms should appear regardless of GLOSSARY_CATEGORIES config."""
    base = {
        "terms": {
            "Lucy": {"category": "characters", "key": "", "source_mappings": {"Korean": "루시"}},
        }
    }
    mod = {
        "terms": {
            "Dark Slash": {"category": "custom", "key": "", "source_mappings": {"Korean": "다크 슬래시"}},
            "Heal Potion": {"category": "items", "key": "", "source_mappings": {"Korean": "힐 포션"}},
        }
    }
    prompt = get_combined_glossary_prompt(base, mod, source_lang="Korean")
    # Base "characters" term should appear (it's in the default allowed categories).
    assert "**Lucy**" in prompt
    # Mod terms in non-default categories should also appear.
    assert "**Dark Slash**" in prompt
    assert "**Heal Potion**" in prompt


def test_combined_glossary_prompt_base_terms_still_filtered():
    """Base glossary terms outside GLOSSARY_CATEGORIES should be filtered out."""
    base = {
        "terms": {
            "Lucy": {"category": "characters", "key": "", "source_mappings": {"Korean": "루시"}},
            "Fire Bolt": {"category": "skills", "key": "", "source_mappings": {"Korean": "화염구"}},
        }
    }
    mod = {"terms": {}}
    prompt = get_combined_glossary_prompt(base, mod, source_lang="Korean")
    # "characters" is in default GLOSSARY_CATEGORIES → included.
    assert "**Lucy**" in prompt
    # "skills" is NOT in default GLOSSARY_CATEGORIES → filtered out.
    assert "**Fire Bolt**" not in prompt


def test_combined_glossary_prompt_mod_overrides_base():
    """When a mod term overrides a base term, only the mod version appears."""
    base = {
        "terms": {
            "Fire": {"category": "buffs/debuffs", "key": "", "source_mappings": {"Korean": "불 (base)"}},
        }
    }
    mod = {
        "terms": {
            "Fire": {"category": "custom", "key": "", "source_mappings": {"Korean": "불 (mod)"}},
        }
    }
    prompt = get_combined_glossary_prompt(base, mod, source_lang="Korean")
    assert "불 (mod)" in prompt
    assert "불 (base)" not in prompt


def test_combined_glossary_prompt_empty_mod():
    """With no mod terms, only filtered base terms appear."""
    base = {
        "terms": {
            "Shield Up": {"category": "mechanics", "key": "", "source_mappings": {"Korean": "방패"}},
        }
    }
    mod = {"terms": {}}
    prompt = get_combined_glossary_prompt(base, mod, source_lang="Korean")
    assert "**Shield Up**" in prompt


def test_get_combined_glossary_prompt_respects_allowed_categories():
    """An explicit allowed_categories overrides config.GLOSSARY_CATEGORIES for the base glossary."""
    from backend.data.glossary_manager import get_combined_glossary_prompt

    base = {
        "terms": {
            "Armour": {"english": "Armour", "category": "stats", "key": "k1", "source_mappings": {"Chinese": "护甲"}},
            "The Black Pit": {"english": "The Black Pit", "category": "regions", "key": "k2", "source_mappings": {"Chinese": "黑暗深渊"}},
        }
    }
    mod = {"terms": {}}

    prompt = get_combined_glossary_prompt(base, mod, source_lang="Chinese", allowed_categories=["stats"])

    assert "Armour" in prompt
    assert "Black Pit" not in prompt


def test_replace_whole_term_only_replaces_whole_words():
    """The old term is replaced where it stands alone, not inside a longer word, and bracketed titles match as a unit."""
    from backend.data.glossary_manager import replace_whole_term

    assert replace_whole_term("Nangao and Nangaoese, Nangao.", "Nangao", "Nangau") == ("Nangau and Nangaoese, Nangau.", 2)
    assert replace_whole_term("the [Lord of Wind] Lidao rides", "[Lord of Wind] Lidao", "[Wind Lord] Lidao") == ("the [Wind Lord] Lidao rides", 1)
    assert replace_whole_term("No match here", "Nangao", "Nangau") == ("No match here", 0)
    assert replace_whole_term("Nangao", "Nangao", "C:\\1 Nangau") == ("C:\\1 Nangau", 1)
