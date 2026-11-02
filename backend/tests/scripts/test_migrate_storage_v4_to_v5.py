"""Tests for the v4->v5 WH3 snapshot-to-history migration."""

import json
from pathlib import Path

from backend.core.settings import settings
from backend.data.history_manager import list_backups, restore_backup
from backend.scripts.migrate_storage_v4_to_v5 import run_migration

WH3 = "total_war_warhammer_3"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_converts_snapshots_into_restorable_history_backups(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "storage_path", tmp_path, raising=True)
    mod = tmp_path / "games" / WH3 / "mods" / "123"
    loc = tmp_path / "source" / "text" / "units.loc.tsv"
    created = "2026-05-25T01:00:00+00:00"
    snapshot = {
        "ulid": "a",
        "created_at": created,
        "label": "pre-sync",
        "kind": "auto",
        "translations_raw": {"k1": {"text": "Hello"}},
        "parent_snapshot": {},
        "api_responses": [],
        "glossary": {"terms": {"Phoenix": {"source": "凤"}}},
        "loc_tsv_files": {str(loc): "old"},
    }
    _write(mod / "snapshots" / "a.json", snapshot)
    _write(mod / "snapshots" / "b.json", {**snapshot, "ulid": "b", "label": "manual save", "kind": "manual"})
    _write(mod / "snapshots" / "index.json", [{"ulid": "a"}, {"ulid": "b"}])

    assert run_migration() is True
    assert run_migration() is False

    backups = list_backups("123", game_id=WH3)
    assert [(b["reason"], b["kind"]) for b in backups] == [("manual save", "manual"), ("pre-sync", "auto")]
    assert backups[1]["id"] == "20260525_010000" and backups[1]["glossary_count"] == 1
    assert not (mod / "snapshots").exists()

    assert restore_backup("123", backups[1]["id"], game_id=WH3) is True
    assert json.loads((mod / "translations.json").read_text(encoding="utf-8")) == {"k1": {"text": "Hello"}}
    assert loc.read_text(encoding="utf-8") == "old"
