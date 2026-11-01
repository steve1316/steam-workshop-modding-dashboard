"""Tests for the v2->v3 storage consolidation migration."""

from pathlib import Path

from backend.core.settings import settings
from backend.scripts.migrate_storage_v2_to_v3 import run_migration


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_moves_legacy_sidecars_into_per_game_namespace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    # Legacy sidecar written by the old buggy routes (freshest).
    _write(tmp_path / "mods" / "123" / "synced_keys.json", '["k1"]')
    _write(tmp_path / "mods" / "123" / "original_csvs" / "Lang.csv", "Key,English\n")
    # Per-game bulk data already present from v1->v2.
    _write(tmp_path / "games" / "chrono_ark" / "mods" / "123" / "translations.json", "{}")

    assert run_migration() is True

    new_mod = tmp_path / "games" / "chrono_ark" / "mods" / "123"
    assert (new_mod / "synced_keys.json").read_text(encoding="utf-8") == '["k1"]'
    assert (new_mod / "original_csvs" / "Lang.csv").read_text(encoding="utf-8") == "Key,English\n"
    assert (new_mod / "translations.json").read_text(encoding="utf-8") == "{}"
    # Legacy mods tree removed once consolidated.
    assert not (tmp_path / "mods").exists()


def test_legacy_sidecar_overwrites_stale_per_game_copy(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    _write(tmp_path / "mods" / "123" / "synced_keys.json", "FRESH")
    _write(tmp_path / "games" / "chrono_ark" / "mods" / "123" / "synced_keys.json", "STALE")

    run_migration()

    assert (tmp_path / "games" / "chrono_ark" / "mods" / "123" / "synced_keys.json").read_text(encoding="utf-8") == "FRESH"


def test_is_idempotent_via_marker(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    _write(tmp_path / "mods" / "123" / "synced_keys.json", "x")
    assert run_migration() is True
    # Second run is a no-op (marker present).
    assert run_migration() is False


def test_no_legacy_dir_is_a_noop(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    # No legacy STORAGE_PATH/mods at all.
    assert run_migration() is True
    assert (tmp_path / "_migrations" / "v2_to_v3_complete.marker").exists()
