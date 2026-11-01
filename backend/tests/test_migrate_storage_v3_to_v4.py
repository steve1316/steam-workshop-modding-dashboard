"""Tests for the v3->v4 provider fold-in migration."""

import json
from pathlib import Path

from backend.core.settings import settings
from backend.scripts.migrate_storage_v3_to_v4 import run_migration


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_folds_providers_into_translations_and_drops_old_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    mod = tmp_path / "games" / "chrono_ark" / "mods" / "123"
    _write(mod / "translations.json", {"k1": {"text": "Hi", "created_at": "t", "updated_at": "t"}, "k2": "Legacy"})
    _write(mod / "translation_providers.json", {"k1": "claude", "k2": "manual", "gone": "ollama"})
    _write(mod / "last_api_responses.json", [])

    assert run_migration() is True

    saved = json.loads((mod / "translations.json").read_text(encoding="utf-8"))
    assert saved["k1"] == {"text": "Hi", "created_at": "t", "updated_at": "t", "provider": "claude"}
    assert saved["k2"] == {"text": "Legacy", "created_at": None, "updated_at": None, "provider": "manual"}
    assert "gone" not in saved
    assert not (mod / "translation_providers.json").exists()
    assert not (mod / "last_api_responses.json").exists()


def test_runs_once(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    assert run_migration() is True
    assert run_migration() is False
