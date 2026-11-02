"""Tests for describing ignored mods on the Settings page."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.settings import settings


def test_ignored_mods_keep_order_and_flag_missing_ones(tmp_path: Path, monkeypatch):
    (tmp_path / "111").mkdir()
    (tmp_path / "111" / "ChronoArkMod.json").write_text(json.dumps({"id": "ViewDeck", "Uploader": "neo"}), encoding="utf-8")
    (tmp_path / "111" / "icon.png").write_bytes(b"")
    monkeypatch.setattr(settings, "workshop_path", tmp_path)
    from backend.app import app

    res = TestClient(app).get("/api/settings/ignored-mods", params={"ids": "222, 111,"})
    assert res.status_code == 200
    missing, installed = res.json()
    assert missing == {
        "id": "222",
        "name": "222",
        "author": "",
        "preview_image": None,
        "url": "https://steamcommunity.com/sharedfiles/filedetails/?id=222",
        "installed": False,
    }
    assert (installed["name"], installed["author"], installed["preview_image"], installed["installed"]) == ("ViewDeck", "neo", "/workshop/111/icon.png", True)
