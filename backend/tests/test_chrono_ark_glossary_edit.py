"""Chrono Ark's mod glossary edit renames the English in existing translations, and edit/delete find a term by its English."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.data.glossary_manager import add_glossary_term, load_mod_glossary, save_mod_glossary
from backend.data.translation_store import load_translations, save_translations_bulk
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.routes import glossary as glossary_routes

MOD_ID = "900000003"
BASE = f"/api/games/chrono_ark/mods/{MOD_ID}/glossary"


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    """TestClient for the Chrono Ark glossary router with storage in tmp_path, three fake strings and a "Kali" term keyed by its source.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: The isolated storage root.

    Returns:
        The test client.
    """
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    # key -> (source text, English from the mod's CSV)
    rows = {"intro": ("卡莉登场", "Kali appears"), "csv_only": ("卡莉", "Kali"), "other": ("别人", "Kali is mentioned")}
    monkeypatch.setattr(glossary_routes, "_source_and_csv_english", lambda mod_id: rows)
    monkeypatch.setattr(glossary_routes, "create_backup", lambda *a, **k: None)
    save_mod_glossary(MOD_ID, add_glossary_term({"terms": {}}, "Kali", {"Chinese": "卡莉"}, "characters"), game_id=GAME_ID)
    app = FastAPI()
    app.include_router(glossary_routes.router, prefix="/api/games/chrono_ark")
    return TestClient(app)


def _terms() -> list[tuple[str, str, dict]]:
    """Return the mod glossary as (english, category, source_mappings) tuples."""
    return [(t["english"], t["category"], t["source_mappings"]) for t in load_mod_glossary(MOD_ID, game_id=GAME_ID)["terms"].values()]


def test_edit_renames_english_in_translations_with_that_source(client: TestClient):
    """Renaming a term's English saves it and replaces it in translations whose source contains the term's source, including CSV-only rows."""
    save_translations_bulk(MOD_ID, {"intro": "Kali appears", "other": "Kali is mentioned"}, game_id=GAME_ID)

    resp = client.put(f"{BASE}/Kali", json={"english": "Kaly", "source_mappings": {"Chinese": "卡莉"}, "category": "characters"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "replaced": 2}
    assert _terms() == [("Kaly", "characters", {"Chinese": "卡莉"})]
    assert load_translations(MOD_ID, game_id=GAME_ID) == {"intro": "Kaly appears", "csv_only": "Kaly", "other": "Kali is mentioned"}


def test_edit_with_a_new_source_replaces_the_old_entry_and_uses_the_old_source(client: TestClient):
    """Changing the source does not leave the old entry behind, and rows are found by the old source."""
    resp = client.put(f"{BASE}/Kali", json={"english": "Kaly", "source_mappings": {"Chinese": "卡莉丝"}, "category": "characters"})
    assert resp.json()["replaced"] == 2
    assert _terms() == [("Kaly", "characters", {"Chinese": "卡莉丝"})]


def test_edit_without_an_english_change_leaves_translations_alone(client: TestClient):
    """A category-only edit changes the glossary but no translation."""
    save_translations_bulk(MOD_ID, {"intro": "Kali appears"}, game_id=GAME_ID)

    resp = client.put(f"{BASE}/Kali", json={"english": "Kali", "source_mappings": {"Chinese": "卡莉"}, "category": "custom"})
    assert resp.json() == {"status": "success", "replaced": 0}
    assert _terms() == [("Kali", "custom", {"Chinese": "卡莉"})]
    assert load_translations(MOD_ID, game_id=GAME_ID) == {"intro": "Kali appears"}


def test_delete_by_english_removes_a_term_keyed_by_its_source(client: TestClient):
    """The modal removes terms by English, which must match a term stored under its source text."""
    resp = client.post(f"{BASE}/delete", json={"terms": ["Kali"]})
    assert resp.json() == {"status": "success", "deleted": 1}
    assert _terms() == []


def test_delete_single_by_english_removes_a_term_keyed_by_its_source(client: TestClient):
    """The single-term DELETE route also accepts the English."""
    client.delete(f"{BASE}/Kali")
    assert _terms() == []
