"""Path helpers keep user-supplied names inside their base directory and resolve per-game storage."""

from pathlib import Path

import pytest

from backend import config
from backend.core.paths import GameStorage, safe_child


def test_plain_names_resolve_under_the_base(tmp_path: Path):
    assert safe_child(tmp_path, "20261101_120000") == tmp_path / "20261101_120000"
    assert safe_child(tmp_path, "LangDataDB.csv") == tmp_path / "LangDataDB.csv"


@pytest.mark.parametrize("name", ["", ".", "..", "../x", "..\\x", "a/b", "a\\b", "C:x", "C:\\x"])
def test_names_that_could_escape_are_rejected(tmp_path: Path, name: str):
    with pytest.raises(ValueError):
        safe_child(tmp_path, name)


def test_game_storage_resolves_under_the_per_game_namespace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "STORAGE_PATH", tmp_path, raising=True)
    storage = GameStorage("chrono_ark")
    assert storage.root == tmp_path / "games" / "chrono_ark"
    assert storage.mods_dir == tmp_path / "games" / "chrono_ark" / "mods"
    assert storage.mod_dir("123") == tmp_path / "games" / "chrono_ark" / "mods" / "123"
    assert storage.mod_file("123", "synced_keys.json") == tmp_path / "games" / "chrono_ark" / "mods" / "123" / "synced_keys.json"


def test_game_storage_keeps_its_game_id():
    assert GameStorage("total_war_warhammer_3").game_id == "total_war_warhammer_3"
