"""Tests for the shared translate-batch pipeline."""

from typing import Any

import pytest

from backend.translation import pipeline
from backend.translation.pipeline import BatchError, BatchJob, BatchOutcome, record_batch, run_translation_batch
from backend.translation.prompt import PromptContext


class _FakeProvider:
    """Provider stub that records its call and returns a fixed result, or raises when `error` is set."""

    def __init__(self, error: str | None = None):
        self.error = error
        self.called_with: dict = {}
        self.last_raw_responses: list = ["stale"]

    def translate_batch(self, entries, source_lang, glossary_prompt, *, game_context, format_rules, style_examples, character_context, target_lang):
        self.called_with = {"entries": entries, "source_lang": source_lang, "glossary_prompt": glossary_prompt, "target_lang": target_lang}
        if self.error:
            raise RuntimeError(self.error)
        self.last_raw_responses = ["raw"]
        # Simulate the LLM deduplicating identical source text: only k1 returned.
        return {"k1": "Hello"}, [{"english": "Hello"}]


@pytest.fixture
def logged(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(pipeline.api_response_log, "log_batch_call", lambda mod_id, **kw: calls.append({"mod_id": mod_id, **kw}))
    return calls


def _job(provider: Any, persisted: list) -> BatchJob:
    def persist(translations, suggestions):
        persisted.append((dict(translations), list(suggestions)))
        return BatchOutcome(translations, suggestions[:0])

    context = PromptContext(source_lang="Chinese", target_lang="English", glossary_prompt="GLOSSARY")
    return BatchJob(mod_id="m1", game_id="g", provider=provider, provider_name="fake", entries=[("k1", "src"), ("k2", "src")], context=context, persist=persist)


def test_run_translation_batch_fills_duplicates_logs_and_persists(logged):
    provider = _FakeProvider()
    persisted: list = []
    outcome = run_translation_batch(_job(provider, persisted))
    assert provider.called_with["source_lang"] == "Chinese"
    assert provider.called_with["glossary_prompt"] == "GLOSSARY"
    assert persisted == [({"k1": "Hello", "k2": "Hello"}, [{"english": "Hello"}])]
    assert outcome.response() == {"status": "success", "translated": 2, "translations": {"k1": "Hello", "k2": "Hello"}, "suggestions": []}
    assert [(c["provider"], c["keys"], c["raw_responses"], c["error"]) for c in logged] == [("fake", ["k1", "k2"], ["raw"], None)]


def test_run_translation_batch_logs_the_error_and_skips_persisting(logged):
    persisted: list = []
    with pytest.raises(BatchError, match="boom"):
        run_translation_batch(_job(_FakeProvider(error="boom"), persisted))
    assert persisted == []
    # The previous batch's raw responses are cleared so they don't land in this batch's log.
    assert [(c["raw_responses"], c["error"]) for c in logged] == [([], "boom")]


def test_record_batch_skips_the_log_when_there_is_nothing_raw(logged):
    provider = _FakeProvider()
    provider.last_raw_responses = []
    persisted: list = []
    record_batch(_job(provider, persisted), {"k1": "Hi"}, [])
    assert persisted == [({"k1": "Hi", "k2": "Hi"}, [])]
    assert logged == []
