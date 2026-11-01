"""Tests for the game-agnostic translation orchestration primitives."""

from backend.translation.orchestrator import chunk_entries, fill_duplicate_translations


def test_fill_duplicate_translations_copies_to_keys_with_shared_source():
    translations = {"k1": "Hello"}
    entries = [("k1", "원본"), ("k2", "원본"), ("k3", "other")]
    fill_duplicate_translations(translations, entries)
    assert translations == {"k1": "Hello", "k2": "Hello"}


def test_fill_duplicate_translations_returns_the_same_dict():
    translations = {"k1": "Hi"}
    result = fill_duplicate_translations(translations, [("k1", "a")])
    assert result is translations


def test_chunk_entries_caps_each_chunk_by_key_count():
    entries = [(f"k{i}", "x") for i in range(5)]
    assert [len(c) for c in chunk_entries(entries, max_keys=2, max_chars=1000)] == [2, 2, 1]


def test_chunk_entries_starts_a_new_chunk_before_the_char_budget_is_exceeded():
    entries = [("k1", "a" * 40), ("k2", "b" * 40), ("k3", "c" * 40)]
    chunks = chunk_entries(entries, max_keys=100, max_chars=100)
    assert [[k for k, _ in c] for c in chunks] == [["k1", "k2"], ["k3"]]


def test_chunk_entries_gives_an_oversized_entry_its_own_chunk():
    entries = [("k1", "a" * 10), ("k2", "b" * 500), ("k3", "c" * 10)]
    chunks = chunk_entries(entries, max_keys=100, max_chars=100)
    assert [[k for k, _ in c] for c in chunks] == [["k1"], ["k2"], ["k3"]]


def test_chunk_entries_returns_no_chunks_for_no_entries():
    assert chunk_entries([], max_keys=10, max_chars=100) == []
