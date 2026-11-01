"""Tests for renaming a glossary term across translations."""

from backend.translation.rename import rename_term, replace_whole_term


def test_replace_whole_term_only_replaces_whole_words():
    """The old term is replaced where it stands alone, not inside a longer word, and bracketed titles match as a unit."""
    assert replace_whole_term("Nangao and Nangaoese, Nangao.", "Nangao", "Nangau") == ("Nangau and Nangaoese, Nangau.", 2)
    assert replace_whole_term("the [Lord of Wind] Lidao rides", "[Lord of Wind] Lidao", "[Wind Lord] Lidao") == ("the [Wind Lord] Lidao rides", 1)
    assert replace_whole_term("No match here", "Nangao", "Nangau") == ("No match here", 0)
    assert replace_whole_term("Nangao", "Nangao", "C:\1 Nangau") == ("C:\1 Nangau", 1)


ROWS = [
    ("k1", "南高城", "the Cathay Phoenix guards Nangao"),
    ("k2", "凤凰", "Cathay Phoenix-Lord"),
    ("k3", "南高", "MetaCathay Phoenix"),
    ("k4", "南高", ""),
]


def test_rename_term_without_source_renames_every_row():
    assert rename_term(ROWS, "Cathay Phoenix", "Cathayan Phoenix") == {"k1": "the Cathayan Phoenix guards Nangao", "k2": "Cathayan Phoenix-Lord"}


def test_rename_term_with_source_only_renames_matching_rows():
    assert rename_term(ROWS, "Cathay Phoenix", "Cathayan Phoenix", source="南高") == {"k1": "the Cathayan Phoenix guards Nangao"}


def test_rename_term_with_empty_source_or_same_english_renames_nothing():
    assert rename_term(ROWS, "Cathay Phoenix", "Cathayan Phoenix", source="") == {}
    assert rename_term(ROWS, "Cathay Phoenix", "Cathay Phoenix") == {}


def test_rename_term_inserts_backslashes_literally():
    assert rename_term(ROWS, "Nangao", "Nan\1gao\\g<0>") == {"k1": "the Cathay Phoenix guards Nan\1gao\\g<0>"}
