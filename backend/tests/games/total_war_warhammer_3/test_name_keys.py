"""Tests for the WH3 name-key classifier used by the 'Translate Names First' pass."""

import pytest

from backend.games.total_war_warhammer_3.translation.name_keys import classify_name_key, is_name_key


@pytest.mark.parametrize(
    "key,expected",
    [
        ("land_units_onscreen_name_cth_inf_dragon_guard", "unit"),
        ("land_units_concealed_name_foo", "unit"),
        ("agent_subtypes_onscreen_name_foo", "unit"),
        ("names_name_1234", "unit"),
        ("unit_abilities_onscreen_name_gouxiang", "skill"),
        ("special_ability_phases_onscreen_name_dashen", "skill"),
        ("character_skills_localised_name_foo", "skill"),
        ("building_culture_variants_name_nangao_workshop", "building"),
        ("battlefield_buildings_names_onscreen_name_foo", "building"),
        ("battlefield_buildings_name_foo", "building"),
        ("building_chains_encyclopedia_name_foo", "building"),
        ("start_pos_settlements_onscreen_name_foo", "location"),
        ("regions_battle_name_foo", "location"),
        ("ancillaries_onscreen_name_foo", "item"),
        ("character_trait_levels_onscreen_name_foo", "trait"),
        ("technologies_onscreen_name_foo", "tech"),
        ("rituals_display_name_foo", "ritual"),
    ],
)
def test_classify_name_key_categories(key: str, expected: str):
    assert classify_name_key(key) == expected


@pytest.mark.parametrize(
    "key",
    [
        "effects_description_effect_unit_cap_cth_inf",
        "unit_description_short_texts_text_cth_inf_dragon",
        "unit_abilities_tooltip_text_gouxiang",
        "building_short_description_texts_short_description_nangao",
        "building_chains_chain_tooltip_nangao_firework_chain",
        "",
        "land_units_onscreen_namex",  # not a token-boundary match
    ],
)
def test_classify_name_key_returns_none_for_non_names(key: str):
    assert classify_name_key(key) is None


def test_is_name_key():
    assert is_name_key("land_units_onscreen_name_x") is True
    assert is_name_key("effects_description_x") is False
