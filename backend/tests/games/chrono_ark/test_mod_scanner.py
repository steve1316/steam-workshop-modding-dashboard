"""Tests for finding one Chrono Ark workshop mod by id."""

import json
from pathlib import Path

from backend.games.chrono_ark.mod_scanner import find_workshop_mod


def _mod(workshop: Path, mod_id: str) -> None:
    (workshop / mod_id).mkdir(parents=True)
    (workshop / mod_id / "ChronoArkMod.json").write_text(json.dumps({"id": f"Mod {mod_id}"}), encoding="utf-8")


def test_finds_the_mod_folder_by_id(tmp_path: Path):
    _mod(tmp_path, "111")
    mod = find_workshop_mod(tmp_path, "111", "ChronoArkMod.json", set())
    assert mod is not None
    assert (mod.mod_id, mod.name, mod.path) == ("111", "Mod 111", tmp_path / "111")


def test_missing_ignored_or_unsafe_ids_are_not_found(tmp_path: Path):
    _mod(tmp_path, "111")
    assert find_workshop_mod(tmp_path, "222", "ChronoArkMod.json", set()) is None
    assert find_workshop_mod(tmp_path, "111", "ChronoArkMod.json", set(), ignored_ids={"111"}) is None
    assert find_workshop_mod(tmp_path / "111", "..", "ChronoArkMod.json", set()) is None
