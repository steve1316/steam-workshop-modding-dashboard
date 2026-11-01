"""Chrono Ark routes are mounted under /api/games/chrono_ark and must use the Chrono Ark adapter.

Regression: the routes resolved their adapter from the persisted `active_game` setting. With WH3 active, the CA
dashboard listed WH3 mods and every CA details page returned 404, which crashed the frontend.
"""

import pytest
from fastapi.testclient import TestClient

from backend.core.settings import settings
from backend.games.base import ModInfo
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.routes import helpers

FAKE_CA_MOD = ModInfo(mod_id="900000001", name="Fake Chrono Ark Mod", author="Tester")


@pytest.fixture
def wh3_active(monkeypatch):
    """Make WH3 the persisted active game and give the Chrono Ark adapter one fake mod.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from backend.games.registry import get_adapter

    monkeypatch.setattr(settings, "active_game", "total_war_warhammer_3")
    # The cached adapter has already rotated to WH3, as it does on a live server after a game switch.
    monkeypatch.setattr(helpers, "_adapter", get_adapter("total_war_warhammer_3"))
    monkeypatch.setattr(ChronoArkAdapter, "scan_mods", lambda self, search_path=None: [FAKE_CA_MOD])


def test_find_mod_uses_chrono_ark_adapter_when_wh3_is_active(wh3_active):
    assert helpers._find_mod(FAKE_CA_MOD.mod_id).name == FAKE_CA_MOD.name


def test_chrono_ark_mod_list_ignores_the_active_game(wh3_active):
    from backend.web_server import app

    res = TestClient(app).get("/api/games/chrono_ark/mods")
    assert res.status_code == 200
    assert [m["id"] for m in res.json()] == [FAKE_CA_MOD.mod_id]
