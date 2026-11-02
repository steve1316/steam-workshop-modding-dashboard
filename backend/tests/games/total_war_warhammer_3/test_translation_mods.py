"""Tests for the WH3 translation mod registry."""

from pathlib import Path

from backend.core.settings import settings
from backend.games.total_war_warhammer_3.adapter import TotalWarWarhammer3Adapter
from backend.games.total_war_warhammer_3.translation.mods import get_translation_mod, translation_mods


def test_unset_folder_lists_no_mods(monkeypatch):
    monkeypatch.setattr(settings.tw3, "translation_mods_path", "  ")
    assert translation_mods() == ()
    assert get_translation_mod("3315737452") is None
    assert TotalWarWarhammer3Adapter().scan_mods() == []


def test_source_dirs_sit_under_the_configured_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.tw3, "translation_mods_path", str(tmp_path))
    mods = translation_mods()
    assert mods
    assert all(m.local_source_dir.parent == Path(tmp_path) for m in mods)
    mod = get_translation_mod("3315737452")
    assert mod is not None
    assert mod.local_source_dir == tmp_path / "Zerooz_English_Translation_corrections"
