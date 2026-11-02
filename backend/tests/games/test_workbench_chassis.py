"""Tests for the multi-game workbench chassis."""

from backend.games.capabilities.translation import TranslationCapability
from backend.games.chrono_ark.adapter import ChronoArkAdapter


def test_chrono_ark_adapter_implements_translation_capability():
    adapter = ChronoArkAdapter()
    assert isinstance(adapter, TranslationCapability)
    assert "translation" in adapter.capabilities


def test_chrono_ark_adapter_has_chassis_metadata():
    adapter = ChronoArkAdapter()
    assert adapter.game_id == "chrono_ark"
    assert adapter.display_name
    assert adapter.icon


def test_list_games_metadata_returns_chrono_ark():
    from backend.games.registry import list_games_metadata

    metadata = list_games_metadata()
    chrono = next((m for m in metadata if m["game_id"] == "chrono_ark"), None)
    assert chrono is not None
    assert chrono["display_name"] == "Chrono Ark"
    assert chrono["icon"] == "chrono_ark"
    assert "translation" in chrono["capabilities"]


def test_api_games_endpoint_lists_chrono_ark():
    from fastapi.testclient import TestClient

    from backend.app import app

    client = TestClient(app)
    res = client.get("/api/games")
    assert res.status_code == 200
    data = res.json()
    chrono = next((g for g in data if g["game_id"] == "chrono_ark"), None)
    assert chrono is not None


def test_tw3_stub_adapter_registered():
    from backend.games.registry import get_adapter, list_games_metadata

    metadata = list_games_metadata()
    tw3 = next((m for m in metadata if m["game_id"] == "total_war_warhammer_3"), None)
    assert tw3 is not None
    assert tw3["display_name"] == "Warhammer III"
    assert tw3["capabilities"] == ["translation"]
    adapter = get_adapter("total_war_warhammer_3")
    assert adapter.game_id == "total_war_warhammer_3"


def test_game_storage_path_resolves_to_per_game_namespace(tmp_path, monkeypatch):
    from backend.core.paths import game_storage_path
    from backend.core.settings import settings

    monkeypatch.setattr(settings, "storage_path", tmp_path)
    assert game_storage_path("chrono_ark") == tmp_path / "games" / "chrono_ark"


def test_migration_moves_legacy_storage(tmp_path, monkeypatch):
    from backend.core.settings import settings
    from backend.migrations.migrate_storage_v1_to_v2 import run_migration

    legacy_root = tmp_path
    (legacy_root / "mods" / "1234").mkdir(parents=True)
    (legacy_root / "mods" / "1234" / "translations.json").write_text("{}", encoding="utf-8")
    (legacy_root / "glossary.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(settings, "storage_path", legacy_root)

    moved = run_migration()
    assert moved is True

    new_root = legacy_root / "games" / "chrono_ark"
    assert (new_root / "mods" / "1234" / "translations.json").exists()
    assert (new_root / "glossary.json").exists()
    assert not (legacy_root / "mods").exists()
    assert (legacy_root / "_migrations" / "v1_complete.marker").exists()


def test_migration_idempotent(tmp_path, monkeypatch):
    from backend.core.settings import settings
    from backend.migrations.migrate_storage_v1_to_v2 import run_migration

    monkeypatch.setattr(settings, "storage_path", tmp_path)
    (tmp_path / "_migrations").mkdir(parents=True)
    (tmp_path / "_migrations" / "v1_complete.marker").write_text("done", encoding="utf-8")

    moved = run_migration()
    assert moved is False


def test_chrono_ark_mods_endpoint_under_game_prefix():
    from fastapi.testclient import TestClient

    from backend.app import app

    client = TestClient(app)
    res = client.get("/api/games/chrono_ark/mods")
    assert res.status_code == 200


def test_post_settings_active_game_rotates_adapter():
    from fastapi.testclient import TestClient

    from backend.app import app
    from backend.routes import helpers

    client = TestClient(app)

    res = client.post("/api/settings", json={"active_game": "total_war_warhammer_3"})
    assert res.status_code == 200
    assert helpers.current_adapter().game_id == "total_war_warhammer_3"

    # Restore so subsequent tests are not polluted.
    res = client.post("/api/settings", json={"active_game": "chrono_ark"})
    assert res.status_code == 200
    assert helpers.current_adapter().game_id == "chrono_ark"
