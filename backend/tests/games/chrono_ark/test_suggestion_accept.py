"""Chrono Ark's suggestion Accept can save an edited English and rename it in the translations whose source contains the term."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.errors import register_error_handler
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.routes import glossary as glossary_routes
from backend.persistence import suggestion_manager
from backend.persistence.glossary_manager import load_mod_glossary
from backend.persistence.translation_store import load_translations, save_translations_bulk

MOD_ID = "900000002"
URL = f"/api/games/chrono_ark/mods/{MOD_ID}/glossary/suggestions/accept"
KALI = {"english": "Kali", "source": "卡莉", "source_lang": "Chinese", "category": "character", "reason": "name"}


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    """TestClient for the Chrono Ark glossary router with storage in tmp_path and three fake strings.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: The isolated storage root.

    Returns:
        The test client.
    """
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    # key -> (source text, English from the mod's CSV)
    rows = {"intro": ("卡莉登场", "Kali appears"), "csv_only": ("卡莉", "Kali"), "other": ("别人", "Kali is mentioned")}
    monkeypatch.setattr(glossary_routes, "_source_and_csv_english", lambda mod_id: rows)
    monkeypatch.setattr(glossary_routes, "create_backup", lambda *a, **k: None)
    app = FastAPI()
    register_error_handler(app)
    app.include_router(glossary_routes.router, prefix="/api/games/chrono_ark")
    return TestClient(app)


def test_accept_with_an_edited_english_renames_translations_with_that_source(client: TestClient):
    """The edited English is saved to the glossary, and rows whose source contains the term's source are renamed, including CSV-only rows."""
    suggestion_manager.save_suggestions(MOD_ID, [KALI], game_id=GAME_ID)
    save_translations_bulk(MOD_ID, {"intro": "Kali appears", "other": "Kali is mentioned"}, game_id=GAME_ID)

    resp = client.post(URL, json={"terms": ["Kali"], "renames": {"Kali": "Kaly"}})
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "accepted": 1, "replaced": 2}
    # Chrono Ark keys its glossary by source text, so check the saved English values.
    assert [t["english"] for t in load_mod_glossary(MOD_ID, game_id=GAME_ID)["terms"].values()] == ["Kaly"]
    assert load_translations(MOD_ID, game_id=GAME_ID) == {"intro": "Kaly appears", "csv_only": "Kaly", "other": "Kali is mentioned"}


def test_accept_without_an_edit_renames_nothing(client: TestClient):
    """Accepting a suggestion as it is keeps today's behavior and reports zero renamed translations."""
    suggestion_manager.save_suggestions(MOD_ID, [KALI], game_id=GAME_ID)
    save_translations_bulk(MOD_ID, {"intro": "Kali appears"}, game_id=GAME_ID)

    resp = client.post(URL, json={"terms": ["Kali"]})
    assert resp.json() == {"status": "success", "accepted": 1, "replaced": 0}
    assert load_translations(MOD_ID, game_id=GAME_ID) == {"intro": "Kali appears"}
