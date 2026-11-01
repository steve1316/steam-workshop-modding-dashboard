"""Tests for the shared local LLM provider flow, run against both Ollama and llama.cpp response shapes."""

import json
from threading import Event

import pytest
import requests

from backend.providers import local_llm_provider
from backend.providers.llamacpp_provider import LlamaCppProvider
from backend.providers.ollama_provider import OllamaProvider

ENTRIES = [("k1", "안녕")]
REPLY = json.dumps({"translations": {"k1": "Hello"}, "suggested_terms": []})


class _FakeResponse:
    def __init__(self, body: dict | None = None, lines: list[str] | None = None):
        self._body = body or {}
        self._lines = lines or []
        self.encoding = None
        self.closed = False

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self) -> None:
        self.closed = True


def _ollama_lines() -> list[str]:
    half = len(REPLY) // 2
    return [
        json.dumps({"message": {"content": REPLY[:half]}}),
        json.dumps({"message": {"content": REPLY[half:]}}),
        json.dumps({"done": True, "prompt_eval_count": 12, "eval_count": 2}),
    ]


def _llamacpp_lines() -> list[str]:
    half = len(REPLY) // 2
    return [
        "data: " + json.dumps({"choices": [{"delta": {"content": REPLY[:half]}}]}),
        ": keep-alive",
        "data: " + json.dumps({"choices": [{"delta": {"content": REPLY[half:]}}]}),
        "data: [DONE]",
    ]


CASES = [
    pytest.param(
        OllamaProvider(base_url="http://ollama", model="qwen"),
        {"message": {"content": REPLY}, "prompt_eval_count": 12, "eval_count": 2},
        _ollama_lines(),
        (12, 2),
        "http://ollama/api/chat",
        id="ollama",
    ),
    pytest.param(
        LlamaCppProvider(base_url="http://llama", model="gemma"),
        {"choices": [{"message": {"content": REPLY}}], "usage": {"prompt_tokens": 12, "completion_tokens": 2}},
        _llamacpp_lines(),
        (None, 2),
        "http://llama/v1/chat/completions",
        id="llamacpp",
    ),
]


@pytest.mark.parametrize(("provider", "body", "lines", "stream_usage", "url"), CASES)
def test_translate_batch_parses_the_reply_and_records_usage(monkeypatch, provider, body, lines, stream_usage, url):
    calls = []
    monkeypatch.setattr(local_llm_provider.requests, "post", lambda u, **kw: calls.append((u, kw)) or _FakeResponse(body=body))
    provider.last_raw_responses = []

    translations, _ = provider.translate_batch(ENTRIES, "Korean", "")

    assert translations == {"k1": "Hello"}
    assert calls[0][0] == url and calls[0][1]["json"]["stream"] is False
    assert (provider.last_raw_responses[0]["input_tokens"], provider.last_raw_responses[0]["output_tokens"]) == (12, 2)


@pytest.mark.parametrize(("provider", "body", "lines", "stream_usage", "url"), CASES)
def test_stream_joins_tokens_and_completes(monkeypatch, provider, body, lines, stream_usage, url):
    monkeypatch.setattr(local_llm_provider.requests, "post", lambda u, **kw: _FakeResponse(lines=lines))

    events = list(provider.translate_batch_stream(ENTRIES, "Korean", ""))

    assert events[0]["type"] == "started"
    complete = events[-1]
    assert complete["type"] == "complete" and complete["translations"] == {"k1": "Hello"}
    assert (complete["input_tokens"], complete["output_tokens"]) == stream_usage


@pytest.mark.parametrize(("provider", "body", "lines", "stream_usage", "url"), CASES)
def test_cancelled_stream_frees_the_gpu(monkeypatch, provider, body, lines, stream_usage, url):
    monkeypatch.setattr(local_llm_provider.requests, "post", lambda u, **kw: _FakeResponse(lines=lines))
    freed = []
    monkeypatch.setattr(type(provider), "_free_gpu", lambda self: freed.append(True))
    cancel = Event()
    cancel.set()

    events = list(provider.translate_batch_stream(ENTRIES, "Korean", "", cancel_event=cancel))

    assert events[-1] == {"type": "cancelled"} and freed == [True]


@pytest.mark.parametrize(("provider", "body", "lines", "stream_usage", "url"), CASES)
def test_unreachable_server_names_it(monkeypatch, provider, body, lines, stream_usage, url):
    def refuse(u, **kw):
        raise requests.ConnectionError

    monkeypatch.setattr(local_llm_provider.requests, "post", refuse)

    with pytest.raises(RuntimeError, match=provider._server_name):
        provider.translate_batch(ENTRIES, "Korean", "")
    assert list(provider.translate_batch_stream(ENTRIES, "Korean", ""))[-1]["type"] == "error"
