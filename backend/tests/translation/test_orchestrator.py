"""Tests for the game-agnostic translation orchestration primitives."""

import asyncio

from backend.translation.orchestrator import chunk_entries, fill_duplicate_translations, run_batch


def test_fill_duplicate_translations_copies_to_keys_with_shared_source():
    translations = {"k1": "Hello"}
    entries = [("k1", "원본"), ("k2", "원본"), ("k3", "other")]
    fill_duplicate_translations(translations, entries)
    assert translations == {"k1": "Hello", "k2": "Hello"}


def test_fill_duplicate_translations_returns_the_same_dict():
    translations = {"k1": "Hi"}
    result = fill_duplicate_translations(translations, [("k1", "a")])
    assert result is translations


class _FakeProvider:
    """Minimal provider stub that records its call and returns a fixed result."""

    def __init__(self):
        self.called_with: dict = {}

    def translate_batch(self, entries, source_lang, glossary_prompt, *, game_context, format_rules, style_examples, character_context, target_lang):
        self.called_with = {"entries": entries, "source_lang": source_lang, "glossary_prompt": glossary_prompt, "target_lang": target_lang}
        # Simulate the LLM deduplicating identical source text: only k1 returned.
        return {"k1": "Hello"}, [{"english": "Hello"}]


def test_run_batch_invokes_provider_then_fills_duplicates():
    provider = _FakeProvider()
    entries = [("k1", "원본"), ("k2", "원본")]
    translations, suggestions = asyncio.run(
        run_batch(
            provider,
            entries,
            "Chinese",
            "GLOSSARY",
            game_context="CONTEXT",
            format_rules=["rule"],
            style_examples={},
            character_context=None,
            target_lang="English",
        )
    )
    assert translations == {"k1": "Hello", "k2": "Hello"}
    assert suggestions == [{"english": "Hello"}]
    assert provider.called_with["source_lang"] == "Chinese"
    assert provider.called_with["glossary_prompt"] == "GLOSSARY"
    assert provider.called_with["target_lang"] == "English"


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
