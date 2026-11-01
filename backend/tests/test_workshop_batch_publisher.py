"""Unit tests for the TW3 SteamCMD `workshop_batch_publisher` orchestrator.

The orchestrator wraps the single-flight `workshop_publisher` with serialized batch semantics.
Tests stub out `workshop_publisher.start_publish` and `stream_lines` so the orchestrator can be
exercised deterministically without spawning real SteamCMD subprocesses.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from pathlib import Path

import pytest

from backend.games.total_war_warhammer_3 import workshop_batch_publisher as wbp
from backend.games.total_war_warhammer_3 import workshop_publisher as wp

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Test helpers


@pytest.fixture(autouse=True)
def _reset_state():
    """Clear orchestrator module state between tests so they don't bleed into each other."""
    wbp._reset_state()
    yield
    wbp._reset_state()


@pytest.fixture(autouse=True)
def _no_real_recorders(monkeypatch):
    """Keep the orchestrator from running the real change note CLI or touching translation baselines."""
    monkeypatch.setattr(wbp.publish_notes, "make_recorder", lambda workshop_id, changenote: None)


def _run(coro: Awaitable):
    """Run a coroutine to completion using a fresh event loop per test."""
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_items(*workshop_ids: str) -> list[dict]:
    """Build the `items` list start_batch accepts (one entry per workshop id, each with its own note)."""
    return [{"workshop_id": wid, "title": f"Mod {wid}", "changenote": f"note {wid}"} for wid in workshop_ids]


def _stub_folder_resolver(monkeypatch, tmp_path: Path, workshop_ids: list[str]) -> dict[str, Path]:
    """Stub `tw3_workshop_content_dir` to return a real tmp folder per workshop id."""
    folders: dict[str, Path] = {}
    for wid in workshop_ids:
        folder = tmp_path / f"content_{wid}"
        folder.mkdir()
        folders[wid] = folder

    def fake_resolver(wid: str) -> Path | None:
        return folders.get(wid)

    monkeypatch.setattr(wbp, "tw3_workshop_content_dir", fake_resolver)
    return folders


def _stub_publisher_success(monkeypatch, stream_events_per_mod: dict[str, list[dict]]):
    """Stub `wp.start_publish` and `wp.stream_lines` so each call returns scripted events.

    Args:
        monkeypatch: pytest fixture.
        stream_events_per_mod: workshop_id -> list of dicts to yield from stream_lines.
            Each list MUST end with `{"event": "done", "exit_code": int, "duration_seconds": float}`.
    """
    call_log: list[dict] = []
    current_id: dict[str, str] = {"id": ""}

    def fake_start_publish(workshop_id, content_folder, changenote, *, steamcmd_path, steam_username, **_kwargs):
        call_log.append(
            {
                "workshop_id": workshop_id,
                "content_folder": str(content_folder),
                "changenote": changenote,
            }
        )
        current_id["id"] = workshop_id

        class _FakeHandle:
            publish_id = f"pub-{workshop_id}"

        return _FakeHandle()

    async def fake_stream_lines() -> AsyncIterator[dict]:
        events = stream_events_per_mod.get(current_id["id"], [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}])
        for evt in events:
            yield evt

    monkeypatch.setattr(wp, "start_publish", fake_start_publish)
    monkeypatch.setattr(wp, "stream_lines", fake_stream_lines)
    monkeypatch.setattr(wp, "is_idle", lambda: True)
    return call_log


async def _start_and_wait(items):
    """Helper: start a batch inside an event loop and await completion."""
    handle = wbp.start_batch(items, steamcmd_path="steamcmd", steam_username="user")
    await handle.done_event.wait()
    return handle


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# start_batch validation


def test_start_batch_rejects_an_item_with_a_blank_changenote(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["1"])
    _stub_publisher_success(monkeypatch, {})
    items = [{"workshop_id": "1", "title": "Mod 1", "changenote": "   "}]

    async def go():
        with pytest.raises(ValueError, match="changenote must not be empty for Mod 1"):
            wbp.start_batch(items, steamcmd_path="steamcmd", steam_username="user")

    _run(go())


def test_start_batch_rejects_empty_items_list(monkeypatch):
    monkeypatch.setattr(wp, "is_idle", lambda: True)

    async def go():
        with pytest.raises(ValueError, match="items"):
            wbp.start_batch([], steamcmd_path="steamcmd", steam_username="user")

    _run(go())


def test_start_batch_rejects_when_single_publish_in_progress(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["1"])
    monkeypatch.setattr(wp, "is_idle", lambda: False)

    async def go():
        with pytest.raises(wbp.BatchInProgressError):
            wbp.start_batch(_make_items("1"), steamcmd_path="steamcmd", steam_username="user")

    _run(go())


def test_start_batch_rejects_when_another_batch_in_progress(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["1", "2"])
    _stub_publisher_success(
        monkeypatch,
        {
            "1": [{"event": "data", "line": "hello", "ts": "t"}, {"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        handle = wbp.start_batch(_make_items("1"), steamcmd_path="steamcmd", steam_username="user")
        with pytest.raises(wbp.BatchInProgressError):
            wbp.start_batch(_make_items("2"), steamcmd_path="steamcmd", steam_username="user")
        await handle.done_event.wait()

    _run(go())


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Sequencing + per-item state


def test_runs_items_sequentially_in_order(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10", "20", "30"])
    calls = _stub_publisher_success(
        monkeypatch,
        {
            "10": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
            "20": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
            "30": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10", "20", "30"))
        assert [c["workshop_id"] for c in calls] == ["10", "20", "30"]
        assert all(item.status == "done" for item in handle.items)
        assert all(item.exit_code == 0 for item in handle.items)

    _run(go())


def test_continues_after_failed_exit_code(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10", "20"])
    _stub_publisher_success(
        monkeypatch,
        {
            "10": [{"event": "done", "exit_code": 1, "duration_seconds": 0.1}],
            "20": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10", "20"))
        assert handle.items[0].status == "failed"
        assert handle.items[0].exit_code == 1
        assert handle.items[1].status == "done"
        assert handle.items[1].exit_code == 0

    _run(go())


def test_continues_after_preflight_error(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10", "20"])

    def fake_start_publish(workshop_id, content_folder, changenote, *, steamcmd_path, steam_username, **_kw):
        if workshop_id == "10":
            raise wp.PublisherPreflightError(["steamcmd_path"])

        class _H:
            publish_id = "pub-20"

        return _H()

    async def fake_stream():
        yield {"event": "done", "exit_code": 0, "duration_seconds": 0.1}

    monkeypatch.setattr(wp, "start_publish", fake_start_publish)
    monkeypatch.setattr(wp, "stream_lines", fake_stream)
    monkeypatch.setattr(wp, "is_idle", lambda: True)

    async def go():
        handle = await _start_and_wait(_make_items("10", "20"))
        assert handle.items[0].status == "failed"
        assert "preflight" in (handle.items[0].error or "").lower()
        assert handle.items[1].status == "done"

    _run(go())


def test_marks_item_failed_when_content_folder_missing(tmp_path, monkeypatch):
    # Only mod 20 has a folder; mod 10 should be marked failed up front.
    _stub_folder_resolver(monkeypatch, tmp_path, ["20"])
    _stub_publisher_success(
        monkeypatch,
        {
            "20": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10", "20"))
        assert handle.items[0].status == "failed"
        assert "folder" in (handle.items[0].error or "").lower()
        assert handle.items[1].status == "done"

    _run(go())


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# SSE event stream


def test_stream_batch_emits_expected_event_sequence(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10"])
    _stub_publisher_success(
        monkeypatch,
        {
            "10": [
                {"event": "data", "line": "uploading", "ts": "2026-01-01T00:00:00"},
                {"event": "data", "line": "done", "ts": "2026-01-01T00:00:01"},
                {"event": "done", "exit_code": 0, "duration_seconds": 1.0},
            ],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10"))
        types = [evt["event"] for evt in handle.events_log]
        assert types[0] == "batch_started"
        assert types[1] == "mod_started"
        assert types.count("log_line") == 2
        assert "mod_finished" in types
        assert types[-1] == "batch_done"

    _run(go())


def test_stream_batch_log_lines_carry_workshop_id(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["42"])
    _stub_publisher_success(
        monkeypatch,
        {
            "42": [
                {"event": "data", "line": "hello", "ts": "t"},
                {"event": "done", "exit_code": 0, "duration_seconds": 0.1},
            ],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("42"))
        log_lines = [evt for evt in handle.events_log if evt["event"] == "log_line"]
        assert log_lines[0]["data"]["workshop_id"] == "42"
        assert log_lines[0]["data"]["line"] == "hello"

    _run(go())


def test_batch_done_summary_counts(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10", "20", "30"])
    _stub_publisher_success(
        monkeypatch,
        {
            "10": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
            "20": [{"event": "done", "exit_code": 1, "duration_seconds": 0.1}],
            "30": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10", "20", "30"))
        final = handle.events_log[-1]
        assert final["event"] == "batch_done"
        assert final["data"]["succeeded"] == 2
        assert final["data"]["failed"] == 1

    _run(go())


def test_stream_batch_replays_backlog_for_late_subscriber(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10"])
    _stub_publisher_success(
        monkeypatch,
        {
            "10": [
                {"event": "data", "line": "line-1", "ts": "t"},
                {"event": "done", "exit_code": 0, "duration_seconds": 0.1},
            ],
        },
    )

    async def go():
        handle = await _start_and_wait(_make_items("10"))
        collected = []
        async for evt in wbp.stream_batch(handle.batch_id):
            collected.append(evt["event"])
        assert collected[0] == "batch_started"
        assert collected[-1] == "batch_done"

    _run(go())


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Registry lookups


def test_current_batch_returns_active_batch(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10"])
    _stub_publisher_success(
        monkeypatch,
        {
            "10": [{"event": "done", "exit_code": 0, "duration_seconds": 0.1}],
        },
    )

    async def go():
        assert wbp.current_batch() is None
        handle = wbp.start_batch(_make_items("10"), steamcmd_path="steamcmd", steam_username="user")
        assert wbp.current_batch() is handle
        await handle.done_event.wait()
        assert wbp.current_batch() is None

    _run(go())


def test_get_batch_returns_none_for_unknown_id():
    assert wbp.get_batch("does-not-exist") is None


def test_each_item_publishes_with_its_own_changenote_and_recorder(tmp_path, monkeypatch):
    _stub_folder_resolver(monkeypatch, tmp_path, ["10", "20"])
    call_log = _stub_publisher_success(monkeypatch, {})
    recorders: dict = {}

    def fake_make_recorder(workshop_id, changenote):
        def recorder(exit_code):
            pass

        recorders[workshop_id] = (changenote, recorder)
        return recorder

    monkeypatch.setattr(wbp.publish_notes, "make_recorder", fake_make_recorder)
    passed_on_exit: dict = {}
    real_fake = wp.start_publish

    def capturing_start_publish(workshop_id, content_folder, changenote, *, on_exit=None, **kwargs):
        passed_on_exit[workshop_id] = on_exit
        return real_fake(workshop_id, content_folder, changenote, **kwargs)

    monkeypatch.setattr(wp, "start_publish", capturing_start_publish)

    async def go():
        return await _start_and_wait(_make_items("10", "20"))

    _run(go())

    assert [c["changenote"] for c in call_log] == ["note 10", "note 20"]
    assert recorders["10"][0] == "note 10"
    assert passed_on_exit == {"10": recorders["10"][1], "20": recorders["20"][1]}
