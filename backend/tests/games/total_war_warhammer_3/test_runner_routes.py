"""Tests for the TW3 runner routes."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.games.total_war_warhammer_3.registry import runner as sr

FIXTURES = Path(__file__).parent / "fixtures" / "helper_scripts"


@pytest.fixture(autouse=True)
def _reset():
    if sr._proc is not None and sr._proc.poll() is None:
        sr.cancel_run()
    sr._current = None
    sr._proc = None
    sr._log.clear()
    yield


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setattr(sr, "SCRIPT_REGISTRY", sr._TEST_SCRIPT_REGISTRY)
    monkeypatch.setattr(
        "backend.games.total_war_warhammer_3.routes.runner._settings",
        lambda: {
            "helper_scripts_path": str(FIXTURES),
            "rpfm_cli_path": str(FIXTURES / "rpfm_cli.exe"),
            "steam_library_drive": "F:",
        },
    )


def test_get_run_when_idle_returns_idle(settings):
    client = TestClient(app)
    res = client.get("/api/games/total_war_warhammer_3/run")
    assert res.status_code == 200
    assert res.json()["status"] == "idle"


def test_post_run_starts_a_run(settings):
    client = TestClient(app)
    res = client.post("/api/games/total_war_warhammer_3/run/_test_echo")
    assert res.status_code == 200
    body = res.json()
    assert body["script_id"] == "_test_echo"
    assert "run_id" in body
    # Allow it to finish.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and sr._proc is not None and sr._proc.poll() is None:
        time.sleep(0.05)


def test_post_run_unknown_script_returns_404(settings):
    client = TestClient(app)
    res = client.post("/api/games/total_war_warhammer_3/run/does_not_exist")
    assert res.status_code == 404


def test_post_run_returns_409_when_already_running(settings):
    client = TestClient(app)
    client.post("/api/games/total_war_warhammer_3/run/_test_sleep")
    res = client.post("/api/games/total_war_warhammer_3/run/_test_echo")
    assert res.status_code == 409


def test_post_run_returns_400_when_preflight_fails(monkeypatch):
    monkeypatch.setattr(sr, "SCRIPT_REGISTRY", sr._TEST_SCRIPT_REGISTRY)
    monkeypatch.setattr(
        "backend.games.total_war_warhammer_3.routes.runner._settings",
        lambda: {"helper_scripts_path": "", "rpfm_cli_path": "", "steam_library_drive": ""},
    )
    client = TestClient(app)
    res = client.post("/api/games/total_war_warhammer_3/run/_test_echo")
    assert res.status_code == 400
    body = res.json()
    assert "missing" in body["detail"]


def test_delete_run_cancels(settings):
    client = TestClient(app)
    client.post("/api/games/total_war_warhammer_3/run/_test_sleep")
    res = client.delete("/api/games/total_war_warhammer_3/run")
    assert res.status_code == 204


def test_run_stream_replays_buffered_lines_and_closes_on_done(settings):
    client = TestClient(app)
    # Start a quick run, wait for it to finish so the buffer is fully populated.
    client.post("/api/games/total_war_warhammer_3/run/_test_echo")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if sr._proc is None or sr._proc.poll() is not None:
            break
        time.sleep(0.05)

    # Now connect to the stream; it should replay all 5 buffered lines + done.
    with client.stream("GET", "/api/games/total_war_warhammer_3/run/stream") as res:
        assert res.status_code == 200
        body = b"".join(res.iter_bytes(chunk_size=1024)).decode()

    # Must contain 5 data events and a terminal done event.
    assert body.count('"line"') >= 5
    assert "event: done" in body
