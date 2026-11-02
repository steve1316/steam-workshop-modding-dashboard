"""Tests for WH3 translation routes.

These tests use FastAPI's `TestClient` and a monkeypatched extractor so they
do not require RPFM CLI or local workshop directories.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.errors import register_error_handler
from backend.games.total_war_warhammer_3 import GAME_ID
from backend.games.total_war_warhammer_3.loc.extractor import LocRow
from backend.games.total_war_warhammer_3.routes import translation as routes_module
from backend.games.total_war_warhammer_3.translation import workspace
from backend.games.total_war_warhammer_3.translation.mods import WH3TranslationMod
from backend.persistence import translation_store


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    # `mods_path()` reads `settings.storage_path` at call time, so this reroutes every store call to a per-test tmp dir.
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)

    # Stub the heavy I/O extractors with deterministic data.
    def fake_parent(mod) -> dict[str, dict[str, LocRow]]:
        return {"a.loc.tsv": {"k1": LocRow("k1", "原文", True), "k2": LocRow("k2", "新文本", True)}}

    def fake_translation(mod) -> dict[str, dict[str, LocRow]]:
        return {"a.loc.tsv": {"k1": LocRow("k1", "Old translation", True)}}

    monkeypatch.setattr(workspace, "extract_parent_strings", fake_parent)
    monkeypatch.setattr(workspace, "extract_translation_strings", fake_translation)

    # Default to "no workshop folder on disk" so preview-image tests are deterministic and don't
    # depend on whatever Steam content the dev machine happens to have installed.
    monkeypatch.setattr(routes_module, "_find_parent_preview_image", lambda mod: None)

    app = FastAPI()
    register_error_handler(app)
    app.include_router(routes_module.router, prefix="/api/games/total_war_warhammer_3")
    return TestClient(app)


def test_list_translation_mods_returns_registry(client: TestClient):
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert {m["workshop_id"] for m in data} == {
        "3315737452",
        "3317696617",
        "3392058226",
        "3393724674",
        "3393724734",
    }


def test_rescan_returns_drift_summary(client: TestClient):
    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    assert resp.status_code == 200
    summary = resp.json()
    # 1 translated (k1), 1 untranslated (k2)
    assert summary["counts"]["translated"] == 1
    assert summary["counts"]["untranslated"] == 1
    assert summary["counts"]["stale"] == 0
    assert summary["counts"]["orphan"] == 0


def test_rescan_counts_skip_blank_source_rows(client: TestClient, monkeypatch):
    # A key whose parent source is blank has nothing to translate, so it must not inflate the progress counts.
    def fake_parent(mod) -> dict[str, dict[str, LocRow]]:
        return {"a.loc.tsv": {"k1": LocRow("k1", "原文", True), "k2": LocRow("k2", "新文本", True), "k3": LocRow("k3", "", True)}}

    def fake_translation(mod) -> dict[str, dict[str, LocRow]]:
        return {"a.loc.tsv": {"k1": LocRow("k1", "Old translation", True), "k3": LocRow("k3", "", True)}}

    monkeypatch.setattr(workspace, "extract_parent_strings", fake_parent)
    monkeypatch.setattr(workspace, "extract_translation_strings", fake_translation)

    summary = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan").json()
    assert summary["counts"]["translated"] == 1
    assert summary["counts"]["untranslated"] == 1


def test_get_strings_filters_by_status(client: TestClient):
    client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/strings?status=untranslated")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["key"] == "k2"
    assert rows[0]["status"] == "untranslated"
    # New: each row now has a `provider` field.
    assert "provider" in rows[0]


def test_get_strings_overlay_from_translations_json(client: TestClient):
    """Verify `get_strings` overlays `translations.json` onto drift rows.

    A key with no `.loc.tsv` translation but a seeded `translations.json` entry should appear as translated with the seeded text and provider.
    """
    now = datetime.now(UTC).isoformat()
    translation_store.save_translations_raw(
        "3315737452",
        {"k2": {"text": "Seeded", "provider": "claude", "created_at": now, "updated_at": now}},
        game_id=GAME_ID,
    )

    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/strings")
    assert resp.status_code == 200
    rows = {r["key"]: r for r in resp.json()}
    assert rows["k2"]["translation_text"] == "Seeded"
    assert rows["k2"]["provider"] == "claude"
    assert rows["k2"]["status"] == "translated"
    # Canonical: a seeded override not yet written to .loc.tsv is an unsynced edit -> pending.
    assert rows["k2"]["canonical_status"] == "pending"


def test_get_strings_includes_canonical_status(client: TestClient):
    """Each row carries the canonical 5-state status alongside the drift status."""
    client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    rows = {r["key"]: r for r in client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/strings").json()}
    # k1 has an on-disk .loc.tsv translation matching the snapshot -> synced.
    assert rows["k1"]["canonical_status"] == "synced"
    # k2 has parent text but no translation -> missing.
    assert rows["k2"]["canonical_status"] == "missing"


def test_put_string_persists_translation(client: TestClient):
    client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    resp = client.put(
        "/api/games/total_war_warhammer_3/translation/mods/3315737452/strings/k2",
        json={"text": "New translation"},
    )
    assert resp.status_code == 200

    # Translated set should now include k2 after a fresh rescan.
    client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan").json()
    # k2 still untranslated because we save into translations.json which is read by
    # extract_translation_strings, but the stub ignores that. So just check persistence:
    assert translation_store.load_translations("3315737452", game_id=GAME_ID)["k2"] == "New translation"
    raw = translation_store.load_translations_raw("3315737452", game_id=GAME_ID)
    assert raw["k2"]["provider"] == "manual"


def test_get_strings_404s_for_unknown_mod(client: TestClient):
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/999/strings")
    assert resp.status_code == 404


def test_mod_context_round_trip(client: TestClient):
    put = client.put(
        "/api/games/total_war_warhammer_3/translation/mods/3315737452/mod-context",
        json={"source_game": "WH3", "character_name": "Zerooz Cathy", "background": "Cathay units."},
    )
    assert put.status_code == 200
    got = client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/mod-context").json()
    assert got["character_name"] == "Zerooz Cathy"
    assert got["background"] == "Cathay units."


def test_list_includes_preview_image_url_field(client: TestClient):
    # Default fixture has no workshop folders on disk so preview URLs resolve to None.
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods")
    assert resp.status_code == 200
    data = resp.json()
    for entry in data:
        assert "preview_image_url" in entry
        assert entry["preview_image_url"] is None


def test_rescan_reports_has_unsynced_changes_false_when_translations_match(client: TestClient):
    # Trigger rescan with no translations.json on disk - nothing unsynced.
    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    assert resp.status_code == 200
    assert resp.json()["has_unsynced_changes"] is False


def test_rescan_reports_has_unsynced_changes_true_when_translations_diverge(client: TestClient, tmp_path: Path):
    # Seed translations.json with text that does NOT match the fake .loc.tsv for k1.
    mod_dir = tmp_path / "games" / "total_war_warhammer_3" / "mods" / "3315737452"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "translations.json").write_text(json.dumps({"k1": {"text": "Different text", "provider": "manual"}}), encoding="utf-8")

    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    assert resp.status_code == 200
    assert resp.json()["has_unsynced_changes"] is True


def test_preview_route_404s_when_no_image_on_disk(client: TestClient):
    # Fixture has no workshop folders on disk; preview lookup returns None.
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/preview")
    assert resp.status_code == 404


def test_preview_route_404s_for_unknown_mod(client: TestClient):
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/9999999999/preview")
    assert resp.status_code == 404


def test_open_folder_calls_subprocess(client: TestClient, monkeypatch, tmp_path: Path):
    fake_source = tmp_path / "translation_mod_source"
    fake_source.mkdir(parents=True, exist_ok=True)
    fake_mod = WH3TranslationMod(
        workshop_id="3315737452",
        display_name="Test Mod",
        parent_workshop_ids=("p",),
        local_source_dir=fake_source,
    )
    monkeypatch.setattr(
        "backend.games.total_war_warhammer_3.routes.translation.get_translation_mod",
        lambda mid: fake_mod if mid == "3315737452" else None,
    )

    opened: list[Path] = []
    monkeypatch.setattr(routes_module, "open_path", opened.append)
    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/open-folder")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert opened == [fake_source]


def test_open_folder_404s_when_source_dir_missing(client: TestClient, monkeypatch, tmp_path: Path):
    fake_mod = WH3TranslationMod(
        workshop_id="3315737452",
        display_name="x",
        parent_workshop_ids=("p",),
        local_source_dir=tmp_path / "does_not_exist",
    )
    monkeypatch.setattr(
        "backend.games.total_war_warhammer_3.routes.translation.get_translation_mod",
        lambda mid: fake_mod if mid == "3315737452" else None,
    )

    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/open-folder")
    assert resp.status_code == 404


def test_rescan_reports_has_mod_context(client: TestClient, tmp_path: Path):
    # Empty mod-context -> has_mod_context: False.
    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    assert resp.status_code == 200
    assert resp.json()["has_mod_context"] is False

    # Save a non-empty mod-context, rescan again -> True.
    client.put(
        "/api/games/total_war_warhammer_3/translation/mods/3315737452/mod-context",
        json={"source_game": "", "character_name": "Zerooz", "background": ""},
    )
    resp = client.post("/api/games/total_war_warhammer_3/translation/mods/3315737452/rescan")
    assert resp.status_code == 200
    assert resp.json()["has_mod_context"] is True


def test_mod_context_round_trips_language_overrides(client: TestClient):
    # PUT with both overrides set, then GET round-trips them.
    client.put(
        "/api/games/total_war_warhammer_3/translation/mods/3315737452/mod-context",
        json={
            "source_game": "",
            "character_name": "",
            "background": "",
            "source_language_override": "Japanese",
            "target_language_override": "English",
        },
    )
    resp = client.get("/api/games/total_war_warhammer_3/translation/mods/3315737452/mod-context")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_language_override"] == "Japanese"
    assert body["target_language_override"] == "English"


def test_get_base_glossary_returns_terms(client: TestClient, tmp_path: Path, monkeypatch):
    """GET /glossary returns the base glossary written to storage."""
    import json

    gpath = tmp_path / "games" / "total_war_warhammer_3" / "glossary.json"
    gpath.parent.mkdir(parents=True, exist_ok=True)
    gpath.write_text(json.dumps({"terms": {"Armour": {"english": "Armour", "category": "stats", "key": "k", "source_mappings": {"Chinese": "护甲"}}}}), encoding="utf-8")

    resp = client.get("/api/games/total_war_warhammer_3/translation/glossary")
    assert resp.status_code == 200
    assert resp.json()["terms"]["Armour"]["category"] == "stats"


def test_get_base_glossary_empty_when_unbuilt(client: TestClient):
    resp = client.get("/api/games/total_war_warhammer_3/translation/glossary")
    assert resp.status_code == 200
    assert resp.json() == {"terms": {}}
