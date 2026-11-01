"""Tests for the WH3 API responses audit log."""

from pathlib import Path

from backend.games.total_war_warhammer_3.api_responses_store import append, list_entries


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
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    append("abc", _entry())
    entries = list_entries("abc")
    assert len(entries) == 1
    assert entries[0]["kind"] == "translate-batch"


def test_list_returns_most_recent_first(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    for i in range(3):
        append("abc", _entry(text=f"entry-{i}"))
    entries = list_entries("abc")
    assert entries[0]["raw_response"] == "entry-2"
    assert entries[-1]["raw_response"] == "entry-0"


def test_append_caps_at_20(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    for i in range(25):
        append("abc", _entry(text=f"entry-{i}"))
    entries = list_entries("abc")
    assert len(entries) == 20
    # Newest first: most recent five (entry-20 .. entry-24).
    assert entries[0]["raw_response"] == "entry-24"
    assert entries[-1]["raw_response"] == "entry-5"


def test_list_empty_when_no_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    assert list_entries("nope") == []
