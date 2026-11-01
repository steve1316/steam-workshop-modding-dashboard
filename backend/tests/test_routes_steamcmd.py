"""Tests for the SteamCMD installer route."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend import config
from backend.routes import steamcmd as steamcmd_routes
from backend.web_server import app


def test_install_returns_path_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_PATH", tmp_path)
    monkeypatch.setattr(config, "STEAMCMD_PATH", "")

    captured: dict = {}
    fake_exe = tmp_path / "steamcmd" / "steamcmd.exe"

    async def fake_install(target_dir: Path) -> Path:
        captured["target_dir"] = target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        fake_exe.write_text("")
        return fake_exe

    monkeypatch.setattr(steamcmd_routes, "install_steamcmd", fake_install)
    monkeypatch.setattr(steamcmd_routes, "update_env_file", lambda updates: None)

    res = TestClient(app).post("/api/steamcmd/install")
    assert res.status_code == 200
    assert res.json() == {"path": str(fake_exe)}
    assert captured["target_dir"] == tmp_path / "steamcmd"
    assert config.STEAMCMD_PATH == str(fake_exe)


def test_install_returns_500_when_installer_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_PATH", tmp_path)

    async def fake_install(target_dir: Path) -> Path:
        raise RuntimeError("download failed: HTTP 503")

    monkeypatch.setattr(steamcmd_routes, "install_steamcmd", fake_install)
    monkeypatch.setattr(steamcmd_routes, "update_env_file", lambda updates: None)

    res = TestClient(app).post("/api/steamcmd/install")
    assert res.status_code == 500
    assert "download failed" in res.json()["detail"]
