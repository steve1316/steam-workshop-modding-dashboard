"""Tests for `space_pinyin_names`, which splits joined pinyin names in WH3 translations into one capitalized word per syllable."""

import pytest

from backend.games.total_war_warhammer_3.translation.name_spacing import glossary_words, space_pinyin_names


@pytest.mark.parametrize(
    ("source", "english", "expected"),
    [
        ("『狂飙烈风之主』妙影", "[Lord of Raging Gale] Miaoying", "[Lord of Raging Gale] Miao Ying"),
        # Place names in a title are split too (上阳 is a place).
        ("『上阳之主』昭明", "[Lord of Shangyang] Zhaoming", "[Lord of Shang Yang] Zhao Ming"),
        ("『巨龙舰队提督』胤隐", "[Dragon Fleet Admiral] Yinyin", "[Dragon Fleet Admiral] Yin Yin"),
        ("烛龙", "Zhulong", "Zhu Long"),
    ],
)
def test_splits_the_users_examples(source: str, english: str, expected: str):
    """The joined names the user reported come back with each syllable as its own word."""
    assert space_pinyin_names(source, english) == expected


def test_splits_names_inside_a_sentence_and_keeps_possessives():
    """A joined name in running text is split, and a possessive stays attached to the last syllable."""
    assert space_pinyin_names("南皋的火器胜过了妙影。", "Nangao's firearms outclassed Miaoying.") == "Nan Gao's firearms outclassed Miao Ying."


def test_keeps_names_the_glossary_spells_joined():
    """A joined word from a glossary term ("Fu Yuanshan") is not split, while other joined names in the row still are."""
    keep = glossary_words(["[Dragon General] Fu Yuanshan", "Great Bastion"])
    assert space_pinyin_names("傅远山与妙影", "Fu Yuanshan and Miaoying", keep=keep) == "Fu Yuanshan and Miao Ying"


def test_uses_any_reading_of_a_character_with_several():
    """A character with more than one reading (长 is chang or zhang) matches whichever one the translation used."""
    assert space_pinyin_names("长垣", "Changyuan") == "Chang Yuan"


def test_keeps_markup_around_the_name():
    """Colour and icon tags around a name are kept as they are."""
    source = "[[col:red]][[img:ui/x.png]][[/img]]烛龙[[/col]]"
    english = "[[col:red]][[img:ui/x.png]][[/img]]Zhulong[[/col]]"
    assert space_pinyin_names(source, english) == "[[col:red]][[img:ui/x.png]][[/img]]Zhu Long[[/col]]"


@pytest.mark.parametrize(
    ("source", "english"),
    [
        ("妙影", "Miao Ying"),
        ("巨龙", "Great Dragon"),
        ("龙卫", "Miaoying"),
        ("妙影", "the miaoying style"),
        ("上阳", "Shang-Yang"),
        ("南皋", "Nangau"),
        ("龙", "Long"),
        ("", "Miaoying"),
    ],
)
def test_leaves_text_alone_when_it_is_not_a_joined_name_from_the_source(source: str, english: str):
    """Spaced names, English words, names whose characters are not in the source, lowercase words, hyphenated names, hand-edited spellings and
    single syllables are unchanged."""
    assert space_pinyin_names(source, english) == english
