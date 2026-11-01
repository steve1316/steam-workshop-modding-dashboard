"""Tests for the per-mod API call log."""

from pathlib import Path

from backend.data.api_response_log import MAX_ENTRIES, append, list_entries, log_batch_call

GAME_ID = "total_war_warhammer_3"


def _root(tmp_path: Path) -> Path:
    return tmp_path / "games" / "total_war_warhammer_3"


def _entry(kind: str = "translate-batch", text: str = "raw") -> dict:
    return {
        "timestamp": "2026-05-25T00:00:00Z",
        "kind": kind,
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.001,
        "keys_or_inputs": ["k1", "k2"],
        "raw_response": text,
    }


def test_append_creates_file_with_first_entry(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    append("abc", _entry(), game_id=GAME_ID)
    entries = list_entries("abc", game_id=GAME_ID)
    assert len(entries) == 1
    assert entries[0]["kind"] == "translate-batch"


def test_list_returns_most_recent_first(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    for i in range(3):
        append("abc", _entry(text=f"entry-{i}"), game_id=GAME_ID)
    entries = list_entries("abc", game_id=GAME_ID)
    assert entries[0]["raw_response"] == "entry-2"
    assert entries[-1]["raw_response"] == "entry-0"


def test_append_keeps_only_the_newest_entries(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    for i in range(MAX_ENTRIES + 5):
        append("abc", _entry(text=f"entry-{i}"), game_id=GAME_ID)
    entries = list_entries("abc", game_id=GAME_ID)
    assert len(entries) == MAX_ENTRIES
    assert entries[0]["raw_response"] == f"entry-{MAX_ENTRIES + 4}"
    assert entries[-1]["raw_response"] == "entry-5"


def test_list_empty_when_no_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    assert list_entries("nope", game_id=GAME_ID) == []


def test_log_batch_call_sums_split_responses(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    raw = [
        {"model": "m", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01, "stop_reason": "end_turn", "raw_text": "a"},
        {"model": "m", "input_tokens": 20, "output_tokens": 7, "cost_usd": 0.02, "stop_reason": "end_turn", "raw_text": "b"},
    ]
    log_batch_call("abc", game_id="chrono_ark", provider="ollama", keys=["k1"], raw_responses=raw)
    [entry] = list_entries("abc", game_id="chrono_ark")
    assert entry["kind"] == "translate-batch"
    assert entry["provider"] == "ollama"
    assert (entry["input_tokens"], entry["output_tokens"]) == (30, 12)
    assert entry["keys_or_inputs"] == ["k1"]
    assert "--- Response 2" in entry["raw_response"]
