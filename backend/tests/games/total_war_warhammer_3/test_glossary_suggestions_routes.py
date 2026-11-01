"""Tests for the WH3 glossary-suggestion review endpoints (accept / dismiss).

These endpoints back the shared `GlossarySuggestionModal` so WH3's iterative translate loop pauses for glossary review exactly like Chrono Ark.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.data import suggestion_manager
from backend.games.storage_paths import game_storage_path
from backend.games.total_war_warhammer_3 import glossary_store
from backend.games.total_war_warhammer_3.api_responses_store import list_entries
from backend.games.total_war_warhammer_3.routes import glossary_suggestions as gs_module
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod
from fastapi import FastAPI
from fastapi.testclient import TestClient

GAME_ID = "total_war_warhammer_3"
MOD_ID = "3315737452"

SUGGESTIONS = [
    {"english": "Lord", "source": "卿", "source_lang": "Chinese", "category": "title", "reason": "recurring honorific"},
    {"english": "Cathay", "source": "震旦", "source_lang": "Chinese", "category": "faction", "reason": "place name"},
]


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    """TestClient for the no-prefix glossary-suggestions router with all I/O isolated to tmp_path."""
    monkeypatch.setattr("backend.config.STORAGE_PATH", tmp_path, raising=True)
    fake_source = tmp_path / "translation_mod_source"
    (fake_source / "text").mkdir(parents=True, exist_ok=True)
    fake_mod = WH3TranslationMod(workshop_id=MOD_ID, display_name="Test Mod", parent_workshop_ids=("p",), local_source_dir=fake_source)
    monkeypatch.setattr(gs_module, "get_translation_mod", lambda mid: fake_mod if mid == MOD_ID else None)
    app = FastAPI()
    app.include_router(gs_module.router, prefix="/api/games/total_war_warhammer_3")
    return TestClient(app)


def _seed_pending(suggestions: list[dict]) -> None:
    suggestion_manager.save_suggestions(MOD_ID, suggestions, storage_path=game_storage_path(GAME_ID))


def _remaining_terms() -> set[str]:
    return {s["english"] for s in suggestion_manager.load_suggestions(MOD_ID, storage_path=game_storage_path(GAME_ID))}


def test_accept_specific_term_adds_to_glossary_and_removes_pending(client: TestClient):
    _seed_pending(SUGGESTIONS)
    resp = client.post(f"/api/games/total_war_warhammer_3/mods/{MOD_ID}/glossary/suggestions/accept", json={"terms": ["Lord"]})
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "accepted": 1, "replaced": 0}
    glossary = glossary_store.load_glossary(MOD_ID)
    assert glossary["Lord"] == {"source": "卿", "category": "title"}
    assert "Cathay" not in glossary
    assert _remaining_terms() == {"Cathay"}


def test_accept_all_adds_every_term_and_clears_pending(client: TestClient):
    _seed_pending(SUGGESTIONS)
    resp = client.post(f"/api/games/total_war_warhammer_3/mods/{MOD_ID}/glossary/suggestions/accept", json={"all": True})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 2
    assert {"Lord", "Cathay"} <= set(glossary_store.load_glossary(MOD_ID))
    assert _remaining_terms() == set()


def test_dismiss_specific_removes_pending_without_touching_glossary(client: TestClient):
    _seed_pending(SUGGESTIONS)
    resp = client.post(f"/api/games/total_war_warhammer_3/mods/{MOD_ID}/glossary/suggestions/dismiss", json={"terms": ["Lord"]})
    assert resp.status_code == 200
    assert glossary_store.load_glossary(MOD_ID) == {}
    assert _remaining_terms() == {"Cathay"}


def test_dismiss_all_clears_pending(client: TestClient):
    _seed_pending(SUGGESTIONS)
    resp = client.post(f"/api/games/total_war_warhammer_3/mods/{MOD_ID}/glossary/suggestions/dismiss", json={"all": True})
    assert resp.status_code == 200
    assert _remaining_terms() == set()


def test_accept_unknown_mod_returns_404(client: TestClient):
    resp = client.post("/api/games/total_war_warhammer_3/mods/unknown/glossary/suggestions/accept", json={"all": True})
    assert resp.status_code == 404


BASE = f"/api/games/total_war_warhammer_3/mods/{MOD_ID}"


class FakeClaude:
    """Stands in for `ClaudeProvider` and returns canned suggested terms."""

    suggestions: list[dict] = []

    def translate_batch(self, entries, source_lang, glossary_prompt, **kwargs):
        """Return no translations and the canned suggestions.

        Args:
            entries: Ignored key/source pairs.
            source_lang: Ignored source language.
            glossary_prompt: Ignored prompt.
            **kwargs: Ignored extras.

        Returns:
            An empty translation dict and the canned suggestions.
        """
        return {}, list(self.suggestions)


@pytest.fixture
def fake_claude(monkeypatch):
    """Route Claude calls and parent extraction through fakes so no API call is made.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The fake provider class, whose `suggestions` each test sets.
    """
    FakeClaude.suggestions = []
    monkeypatch.setattr(gs_module, "ClaudeProvider", FakeClaude)
    monkeypatch.setattr(gs_module, "_extract_all_parent_strings", lambda mod: {"units.loc.tsv": {"k1": SimpleNamespace(text="震旦凤")}})
    return FakeClaude


def test_get_suggestions_returns_the_pending_list(client: TestClient):
    _seed_pending(SUGGESTIONS)
    resp = client.get(f"{BASE}/glossary/suggestions")
    assert resp.status_code == 200
    assert {s["english"] for s in resp.json()} == {"Lord", "Cathay"}


def test_scan_saves_new_terms_and_skips_ones_already_in_the_glossary(client: TestClient, fake_claude):
    glossary_store.add_term(MOD_ID, {"english": "Cathay", "source": "震旦", "category": "faction"})
    fake_claude.suggestions = [dict(SUGGESTIONS[1]), dict(SUGGESTIONS[0])]
    resp = client.post(f"{BASE}/glossary/suggestions/scan")
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "new": 1}
    assert _remaining_terms() == {"Lord"}
    assert any(e["kind"] == "scan-terms" for e in list_entries(MOD_ID))


def test_scan_does_not_duplicate_a_term_that_is_already_pending(client: TestClient, fake_claude):
    _seed_pending([SUGGESTIONS[0]])
    fake_claude.suggestions = [dict(SUGGESTIONS[0])]
    resp = client.post(f"{BASE}/glossary/suggestions/scan")
    assert resp.json()["new"] == 0
    assert _remaining_terms() == {"Lord"}


def test_suggest_edits_saves_suggestions_for_review(client: TestClient, fake_claude):
    glossary_store.add_term(MOD_ID, {"english": "Chongtang", "source": "祟唐", "category": "character"})
    fake_claude.suggestions = [{"english": "[Sentinel] Suitang", "source": "『戍望』祟唐", "source_lang": "Chinese", "category": "character", "reason": "title", "edit_of": "Chongtang"}]
    resp = client.post(f"{BASE}/glossary/suggest-edits")
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "new": 1}
    # Claude joined the name, and it is saved with spaced syllables.
    assert _remaining_terms() == {"[Sentinel] Sui Tang"}
    assert any(e["kind"] == "suggest-edits" for e in list_entries(MOD_ID))


def test_accepting_an_edit_suggestion_renames_the_old_term(client: TestClient):
    glossary_store.add_term(MOD_ID, {"english": "Chongtang", "source": "祟唐", "category": "character"})
    _seed_pending([{"english": "[Sentinel] Suitang", "source": "『戍望』祟唐", "source_lang": "Chinese", "category": "character", "reason": "title", "edit_of": "Chongtang"}])
    resp = client.post(f"{BASE}/glossary/suggestions/accept", json={"all": True})
    assert resp.status_code == 200
    glossary = glossary_store.load_glossary(MOD_ID)
    assert "Chongtang" not in glossary
    assert glossary["[Sentinel] Suitang"]["source"] == "『戍望』祟唐"


def test_scan_returns_404_for_an_unknown_mod(client: TestClient, fake_claude):
    assert client.post("/api/games/total_war_warhammer_3/mods/999/glossary/suggestions/scan").status_code == 404


def test_suggest_edits_keeps_a_refinement_of_an_existing_term_and_accept_updates_it(client: TestClient, fake_claude):
    # The real provider never sends `edit_of`, so the route must work it out from the existing glossary.
    glossary_store.add_term(MOD_ID, {"english": "Lord", "source": "卿", "category": "custom"})
    fake_claude.suggestions = [{"english": "Lord", "source": "卿", "source_lang": "Chinese", "category": "title", "reason": "better category"}]
    assert client.post(f"{BASE}/glossary/suggest-edits").json()["new"] == 1
    assert client.post(f"{BASE}/glossary/suggestions/accept", json={"all": True}).status_code == 200
    assert glossary_store.load_glossary(MOD_ID)["Lord"]["category"] == "title"


def test_suggest_edits_treats_a_new_name_for_the_same_source_as_a_rename(client: TestClient, fake_claude):
    glossary_store.add_term(MOD_ID, {"english": "Chongtang", "source": "祟唐", "category": "character"})
    fake_claude.suggestions = [{"english": "Suitang", "source": "祟唐", "source_lang": "Chinese", "category": "character", "reason": "correct reading"}]
    assert client.post(f"{BASE}/glossary/suggest-edits").json()["new"] == 1
    client.post(f"{BASE}/glossary/suggestions/accept", json={"all": True})
    glossary = glossary_store.load_glossary(MOD_ID)
    assert "Chongtang" not in glossary
    assert glossary["Sui Tang"]["source"] == "祟唐"


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Accept with an edited English


NANGAO = {"english": "Nangao", "source": "南皋", "source_lang": "Chinese", "category": "location", "reason": "place"}
ACCEPT_URL = f"/api/games/total_war_warhammer_3/mods/{MOD_ID}/glossary/suggestions/accept"


def _seed_rows(monkeypatch, tmp_path: Path, parent: dict[str, str], saved: dict[str, str], pack: dict[str, str] | None = None) -> None:
    """Stub the mod's parent and pack strings and write its translations.json.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: The isolated storage root.
        parent: Key -> source text.
        saved: Key -> English saved in translations.json.
        pack: Key -> English already in the translation pack's `.loc.tsv`.
    """
    import json

    from backend.games.total_war_warhammer_3.loc_extractor import LocRow
    from backend.games.total_war_warhammer_3.routes import translation as tr

    monkeypatch.setattr(tr, "_extract_all_parent_strings", lambda mod: {"units.loc.tsv": {k: LocRow(k, v, True) for k, v in parent.items()}})
    monkeypatch.setattr(tr, "_extract_translation_strings", lambda mod: {"units.loc.tsv": {k: LocRow(k, v, True) for k, v in (pack or {}).items()}})
    mod_dir = tmp_path / "games" / GAME_ID / "mods" / MOD_ID
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "translations.json").write_text(json.dumps({k: {"text": v, "provider": "claude"} for k, v in saved.items()}), encoding="utf-8")


def _saved_english() -> dict[str, str]:
    """Return the English saved in translations.json, keyed by loc key."""
    from backend.games.total_war_warhammer_3 import translation_store_helpers as store

    return {k: v["text"] for k, v in store.load_translations_raw(MOD_ID).items()}


def test_accept_with_an_edited_english_saves_the_edit_and_renames_rows_with_that_source(client: TestClient, monkeypatch, tmp_path: Path):
    """The edited English becomes the glossary term, and only translations whose source contains the term's source are renamed."""
    _seed_pending([NANGAO])
    _seed_rows(
        monkeypatch,
        tmp_path,
        parent={"city": "南皋城", "hub": "南皋", "other": "北方"},
        saved={"city": "Nangao City and the Nangaoese", "hub": "Nangao", "other": "Nangao is only mentioned here"},
    )

    resp = client.post(ACCEPT_URL, json={"terms": ["Nangao"], "renames": {"Nangao": "Nangau"}})
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "accepted": 1, "replaced": 2}
    glossary = glossary_store.load_glossary(MOD_ID)
    assert glossary["Nangau"] == {"source": "南皋", "category": "location"}
    assert "Nangao" not in glossary
    assert _saved_english() == {"city": "Nangau City and the Nangaoese", "hub": "Nangau", "other": "Nangao is only mentioned here"}
    assert _remaining_terms() == set()


def test_accept_with_an_edited_english_renames_rows_only_in_the_pack(client: TestClient, monkeypatch, tmp_path: Path):
    """A translation that exists only in the pack's `.loc.tsv` gets the renamed text saved to translations.json, ready to Sync."""
    _seed_pending([NANGAO])
    _seed_rows(monkeypatch, tmp_path, parent={"hub": "南皋"}, saved={}, pack={"hub": "Nangao"})

    resp = client.post(ACCEPT_URL, json={"terms": ["Nangao"], "renames": {"Nangao": "Nangau"}})
    assert resp.json()["replaced"] == 1
    assert _saved_english() == {"hub": "Nangau"}


def test_accept_all_applies_every_rename(client: TestClient, monkeypatch, tmp_path: Path):
    """Accept All saves each edited English and leaves unedited suggestions as they were."""
    _seed_pending([NANGAO, SUGGESTIONS[1]])
    _seed_rows(monkeypatch, tmp_path, parent={"hub": "南皋", "land": "震旦"}, saved={"hub": "Nangao", "land": "Cathay"})

    resp = client.post(ACCEPT_URL, json={"all": True, "renames": {"Nangao": "Nangau"}})
    assert resp.json() == {"status": "success", "accepted": 2, "replaced": 1}
    assert set(glossary_store.load_glossary(MOD_ID)) == {"Nangau", "Cathay"}
    assert _saved_english() == {"hub": "Nangau", "land": "Cathay"}


def test_accept_ignores_a_blank_rename(client: TestClient, monkeypatch, tmp_path: Path):
    """A rename that is blank or unchanged keeps the suggested English and renames nothing."""
    _seed_pending([NANGAO])
    _seed_rows(monkeypatch, tmp_path, parent={"hub": "南皋"}, saved={"hub": "Nangao"})

    resp = client.post(ACCEPT_URL, json={"terms": ["Nangao"], "renames": {"Nangao": "   "}})
    assert resp.json()["replaced"] == 0
    assert "Nangao" in glossary_store.load_glossary(MOD_ID)
    assert _saved_english() == {"hub": "Nangao"}


def test_scan_splits_joined_names_in_suggested_terms(client: TestClient, fake_claude):
    """Scan for Terms saves a joined pinyin name with spaced syllables."""
    fake_claude.suggestions = [{"english": "Miaoying", "source": "妙影", "source_lang": "Chinese", "category": "character", "reason": "lord"}]
    resp = client.post(f"{BASE}/glossary/suggestions/scan")
    assert resp.json() == {"status": "success", "new": 1}
    assert _remaining_terms() == {"Miao Ying"}
