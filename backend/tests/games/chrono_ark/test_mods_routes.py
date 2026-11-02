"""Chrono Ark mod routes."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.games.base import ModInfo
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.models import LocString

FAKE_MOD = ModInfo(mod_id="900000003", name="Fake Mod", author="Tester", path=Path("fake"))


def test_refresh_streams_progress_then_every_mods_row(monkeypatch):
    from backend.web_server import app

    strings = {"Buff/B_Test_Name": LocString(key="Buff/B_Test_Name", type="Text", desc="", translations={"Korean": "테스트"})}
    monkeypatch.setattr(ChronoArkAdapter, "scan_mods", lambda self, search_path=None: [FAKE_MOD])
    monkeypatch.setattr(ChronoArkAdapter, "find_mod", lambda self, mod_id, search_path=None: FAKE_MOD if mod_id == FAKE_MOD.mod_id else None)
    monkeypatch.setattr(ChronoArkAdapter, "extract_strings", lambda self, path: (strings, {}))

    res = TestClient(app).post("/api/games/chrono_ark/mods/refresh")

    assert res.status_code == 200
    events = [json.loads(line[len("data: ") :]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0] == {"current": 1, "total": 1, "mod_name": "Fake Mod"}
    assert events[-1]["done"] is True
    [row] = events[-1]["results"]
    assert (row["id"], row["total"], row["untranslated"], row["has_changes"]) == (FAKE_MOD.mod_id, 1, 1, False)
