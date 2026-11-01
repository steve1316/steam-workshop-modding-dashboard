"""Tests for the Chrono Ark history manager, focused on the auto/manual kind field."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.data import history_manager
from backend.data.history_manager import create_backup, delete_backup, list_backups, restore_backup


def _seed(tmp_path: Path, mod_id: str) -> Path:
    """Seed a mod dir with a translations.json so a backup has something to capture."""
    mod_dir = tmp_path / "mods" / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "translations.json").write_text(json.dumps({"k1": "Hello"}), encoding="utf-8")
    return mod_dir


def test_create_backup_defaults_to_auto_kind(tmp_path: Path):
    _seed(tmp_path, "abc")
    create_backup("abc", "Before sync", storage_path=tmp_path)
    backups = list_backups("abc", storage_path=tmp_path)
    assert len(backups) == 1
    assert backups[0]["kind"] == "auto"
    assert backups[0]["reason"] == "Before sync"


def test_create_backup_records_manual_kind(tmp_path: Path):
    _seed(tmp_path, "abc")
    create_backup("abc", "My checkpoint", storage_path=tmp_path, kind="manual")
    backups = list_backups("abc", storage_path=tmp_path)
    assert len(backups) == 1
    assert backups[0]["kind"] == "manual"
    assert backups[0]["reason"] == "My checkpoint"


def test_list_backups_backfills_missing_kind_as_auto(tmp_path: Path):
    _seed(tmp_path, "abc")
    backup_id = create_backup("abc", "Old backup", storage_path=tmp_path)
    # Simulate a legacy backup whose meta.json predates the kind field.
    meta_path = tmp_path / "mods" / "abc" / "history" / backup_id / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["kind"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    backups = list_backups("abc", storage_path=tmp_path)
    assert backups[0]["kind"] == "auto"


@pytest.mark.parametrize("backup_id", ["..", ".", "", "../abc", "..\\abc"])
def test_delete_and_restore_ignore_ids_that_leave_the_history_dir(tmp_path: Path, backup_id: str):
    mod_dir = _seed(tmp_path, "abc")
    assert delete_backup("abc", backup_id, storage_path=tmp_path) is False
    assert restore_backup("abc", backup_id, storage_path=tmp_path) is False
    assert (mod_dir / "translations.json").exists()


def test_backups_in_the_same_second_get_their_own_ids(tmp_path: Path, monkeypatch):
    fixed = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(history_manager, "datetime", _FrozenDatetime)
    _seed(tmp_path, "abc")
    first = create_backup("abc", "First", storage_path=tmp_path)
    second = create_backup("abc", "Second", storage_path=tmp_path)

    assert first != second
    assert [b["reason"] for b in list_backups("abc", storage_path=tmp_path)] == ["Second", "First"]


def test_listing_an_unknown_mod_creates_nothing(tmp_path: Path):
    assert list_backups("nope", storage_path=tmp_path) == []
    assert not (tmp_path / "mods" / "nope").exists()


def test_suffixed_backup_id_points_at_its_folder(tmp_path: Path, monkeypatch):
    fixed = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(history_manager, "datetime", _FrozenDatetime)
    _seed(tmp_path, "abc")
    create_backup("abc", "First", storage_path=tmp_path)
    second = create_backup("abc", "Second", storage_path=tmp_path)
    assert (tmp_path / "mods" / "abc" / "history" / second / "meta.json").exists()
    assert delete_backup("abc", second, storage_path=tmp_path) is True
