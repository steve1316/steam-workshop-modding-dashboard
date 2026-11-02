"""Tests for the shared per-mod history backups."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.core.paths import mods_path
from backend.games.chrono_ark import GAME_ID
from backend.persistence import history_manager
from backend.persistence.history_manager import create_backup, delete_backup, list_backups, restore_backup

WH3 = "total_war_warhammer_3"


def _seed(mod_id: str) -> Path:
    """Seed a mod dir with a translations.json so a backup has something to capture."""
    mod_dir = mods_path(GAME_ID) / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "translations.json").write_text(json.dumps({"k1": "Hello"}), encoding="utf-8")
    return mod_dir


def test_create_backup_defaults_to_auto_kind():
    _seed("abc")
    create_backup("abc", "Before sync", game_id=GAME_ID)
    backups = list_backups("abc", game_id=GAME_ID)
    assert len(backups) == 1
    assert backups[0]["kind"] == "auto"
    assert backups[0]["reason"] == "Before sync"


def test_create_backup_records_manual_kind():
    _seed("abc")
    create_backup("abc", "My checkpoint", game_id=GAME_ID, kind="manual")
    backups = list_backups("abc", game_id=GAME_ID)
    assert len(backups) == 1
    assert backups[0]["kind"] == "manual"
    assert backups[0]["reason"] == "My checkpoint"


def test_list_backups_backfills_missing_kind_as_auto():
    _seed("abc")
    backup_id = create_backup("abc", "Old backup", game_id=GAME_ID)
    assert backup_id is not None
    # Simulate a legacy backup whose meta.json predates the kind field.
    meta_path = mods_path(GAME_ID) / "abc" / "history" / backup_id / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["kind"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    backups = list_backups("abc", game_id=GAME_ID)
    assert backups[0]["kind"] == "auto"


@pytest.mark.parametrize("backup_id", ["..", ".", "", "../abc", "..\\abc"])
def test_delete_and_restore_ignore_ids_that_leave_the_history_dir(backup_id: str):
    mod_dir = _seed("abc")
    assert delete_backup("abc", backup_id, game_id=GAME_ID) is False
    assert restore_backup("abc", backup_id, game_id=GAME_ID) is False
    assert (mod_dir / "translations.json").exists()


def test_backups_in_the_same_second_get_their_own_ids(monkeypatch):
    fixed = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(history_manager, "datetime", _FrozenDatetime)
    _seed("abc")
    first = create_backup("abc", "First", game_id=GAME_ID)
    second = create_backup("abc", "Second", game_id=GAME_ID)

    assert first != second
    assert [b["reason"] for b in list_backups("abc", game_id=GAME_ID)] == ["Second", "First"]


def test_listing_an_unknown_mod_creates_nothing():
    assert list_backups("nope", game_id=GAME_ID) == []
    assert not (mods_path(GAME_ID) / "nope").exists()


def test_suffixed_backup_id_points_at_its_folder(monkeypatch):
    fixed = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(history_manager, "datetime", _FrozenDatetime)
    _seed("abc")
    create_backup("abc", "First", game_id=GAME_ID)
    second = create_backup("abc", "Second", game_id=GAME_ID)
    assert second is not None
    assert (mods_path(GAME_ID) / "abc" / "history" / second / "meta.json").exists()
    assert delete_backup("abc", second, game_id=GAME_ID) is True


def test_wh3_backups_capture_and_restore_files_outside_the_mod_dir(tmp_path: Path):
    mod_dir = mods_path(WH3) / "abc"
    mod_dir.mkdir(parents=True)
    (mod_dir / "parent_snapshot.json").write_text(json.dumps({"units.loc.tsv": {}}), encoding="utf-8")
    loc = tmp_path / "source" / "text" / "units.loc.tsv"
    loc.parent.mkdir(parents=True)
    loc.write_text("old", encoding="utf-8")

    backup_id = create_backup("abc", "Before sync", game_id=WH3, extra_files=[loc])
    assert backup_id is not None
    loc.write_text("new", encoding="utf-8")
    (mod_dir / "parent_snapshot.json").write_text("{}", encoding="utf-8")

    assert restore_backup("abc", backup_id, game_id=WH3, extra_files=[loc]) is True
    assert loc.read_text(encoding="utf-8") == "old"
    assert json.loads((mod_dir / "parent_snapshot.json").read_text(encoding="utf-8")) == {"units.loc.tsv": {}}
    assert list_backups("abc", game_id=WH3)[0]["reason"] == f"Before restore to {backup_id}"


def test_restore_resets_chrono_ark_sync_state():
    mod_dir = _seed("abc")
    backup_id = create_backup("abc", "First", game_id=GAME_ID)
    assert backup_id is not None
    (mod_dir / "synced_keys.json").write_text("[]", encoding="utf-8")

    restore_backup("abc", backup_id, game_id=GAME_ID)
    assert not (mod_dir / "synced_keys.json").exists()


def test_backups_are_pruned_to_the_newest_twenty():
    _seed("abc")
    hist = mods_path(GAME_ID) / "abc" / "history"
    for i in range(25):
        (hist / f"2026010{i // 10}_00000{i % 10}").mkdir(parents=True)
    create_backup("abc", "Latest", game_id=GAME_ID)
    assert len([e for e in hist.iterdir() if e.is_dir()]) == history_manager.MAX_BACKUPS
