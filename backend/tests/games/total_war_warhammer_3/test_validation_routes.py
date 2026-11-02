"""Tests for the TW3 validation route."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.settings import settings
from backend.games.total_war_warhammer_3.registry.loader import (
    RegistryFileMissingError,
)
from backend.web_server import app

FIXTURES = Path(__file__).parent / "fixtures" / "helper_scripts"


@pytest.fixture(autouse=True, scope="module")
def _reset_tw3_router_cache():
    """Reset the TW3 adapter's class-level router cache before this module runs.

    `TotalWarWarhammer3Adapter._ROUTER` is a lazy singleton built on first property
    access. If another test module has already triggered that build, the cached
    router won't include the validation sub-router this file exercises. Setting it
    to `None` forces a rebuild on next access.
    """
    from backend.games.total_war_warhammer_3.adapter import TotalWarWarhammer3Adapter

    TotalWarWarhammer3Adapter._ROUTER = None
    yield


def test_get_validation_returns_issues_from_fixture(monkeypatch):
    """Pointing TW3_HELPER_PATH at the test fixtures yields known issues from the fixture mods.

    Args:
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setattr(settings.tw3, "helper_path", str(FIXTURES))
    client = TestClient(app)
    res = client.get("/api/games/total_war_warhammer_3/validation")
    assert res.status_code == 200
    issues = res.json()["issues"]
    assert any(i["kind"] == "missing_effect_category" and i["target"] == "melee" for i in issues)
    assert any(i["kind"] == "missing_mod_path" for i in issues)


def test_get_validation_returns_503_when_helper_path_unset(monkeypatch):
    """Returns 503 when `TW3_HELPER_PATH` is not configured.

    Args:
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setattr(settings.tw3, "helper_path", "")
    client = TestClient(app)
    res = client.get("/api/games/total_war_warhammer_3/validation")
    assert res.status_code == 503


def test_get_validation_returns_503_when_supported_mods_missing(monkeypatch):
    """Returns 503 when `load_supported_mods` raises `RegistryFileMissingError`.

    Args:
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setattr(settings.tw3, "helper_path", "/fake/path")
    client = TestClient(app)
    with patch(
        "backend.games.total_war_warhammer_3.routes.validation.load_supported_mods",
        side_effect=RegistryFileMissingError("supported_mods.py not found"),
    ):
        res = client.get("/api/games/total_war_warhammer_3/validation")
    assert res.status_code == 503
    assert "Registry unavailable" in res.json()["detail"]


def test_get_validation_returns_503_when_effects_missing(monkeypatch):
    """Returns 503 when `load_supported_effects` raises `RegistryFileMissingError`.

    Args:
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setattr(settings.tw3, "helper_path", "/fake/path")
    client = TestClient(app)
    with patch(
        "backend.games.total_war_warhammer_3.routes.validation.load_supported_effects",
        side_effect=RegistryFileMissingError("dynamic_rors_effects.py not found"),
    ):
        res = client.get("/api/games/total_war_warhammer_3/validation")
    assert res.status_code == 503
    assert "Registry unavailable" in res.json()["detail"]


def test_get_validation_returns_empty_when_no_issues(monkeypatch, tmp_path):
    """Returns an empty issues list when all mod paths exist and all categories are valid.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        tmp_path: pytest tmp_path fixture.
    """
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    real_pack = tmp_path / "real_a.pack"
    real_pack.write_bytes(b"x")
    (helper / "data").mkdir()
    (helper / "data" / "supported_mods.py").write_text(f'SUPPORTED_MODS = [{{"name": "OK Mod", "package_name": "ok_mod", "path": "{real_pack.as_posix()}", "modified_attributes": ["infantry"]}}]')
    (helper / "data" / "dynamic_rors_effects.py").write_text('SUPPORTED_EFFECTS = {"infantry": {}}')
    monkeypatch.setattr(settings.tw3, "helper_path", str(helper))
    client = TestClient(app)
    res = client.get("/api/games/total_war_warhammer_3/validation")
    assert res.status_code == 200
    assert res.json() == {"issues": []}
