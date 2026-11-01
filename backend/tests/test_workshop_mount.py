"""Chrono Ark thumbnails are served no matter which game was active at startup."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import web_server
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.routes import helpers


def test_workshop_mount_uses_chrono_ark_even_when_wh3_is_active(tmp_path: Path, monkeypatch):
    (tmp_path / "123").mkdir()
    (tmp_path / "123" / "preview.png").write_bytes(b"png")
    monkeypatch.setattr(ChronoArkAdapter, "_WORKSHOP_PATH", tmp_path)
    monkeypatch.setattr(helpers, "_adapter", helpers.get_adapter("total_war_warhammer_3"))

    app = FastAPI()
    web_server._mount_workshop(app)

    assert TestClient(app).get("/api/workshop/123/preview.png").content == b"png"


def test_missing_workshop_folder_is_skipped(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ChronoArkAdapter, "_WORKSHOP_PATH", tmp_path / "missing")
    app = FastAPI()
    web_server._mount_workshop(app)
    assert not [r for r in app.routes if getattr(r, "name", "") == "workshop"]
