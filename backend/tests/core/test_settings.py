"""Tests for reading settings from SWMT_ env vars."""

from backend.core.settings import Settings


def test_comma_lists_are_split_and_trimmed(monkeypatch):
    monkeypatch.setenv("SWMT_IGNORED_MODS", " 111, 222,,")
    monkeypatch.setenv("SWMT_GLOSSARY_CATEGORIES", "characters,places")
    s = Settings()
    assert s.ignored_mods == ["111", "222"]
    assert s.glossary_categories == ["characters", "places"]


def test_empty_comma_list_is_empty(monkeypatch):
    monkeypatch.setenv("SWMT_IGNORED_MODS", "")
    assert Settings().ignored_mods == []


def test_tw3_section_keeps_the_tw3_env_names(monkeypatch):
    monkeypatch.setenv("SWMT_TW3_HELPER_PATH", "D:/helper_scripts")
    monkeypatch.setenv("SWMT_TW3_STEAM_LIBRARY_DRIVE", "F:")
    s = Settings()
    assert s.tw3.helper_path == "D:/helper_scripts"
    assert s.tw3.steam_library_drive == "F:"


def test_numbers_are_parsed(monkeypatch):
    monkeypatch.setenv("SWMT_BATCH_SIZE", "25")
    monkeypatch.setenv("SWMT_LLAMACPP_GPU_LAYERS", "-1")
    s = Settings()
    assert s.batch_size == 25
    assert s.llamacpp_gpu_layers == -1


def test_game_paths_have_no_machine_default(monkeypatch):
    monkeypatch.delenv("SWMT_BASE_GAME_PATH", raising=False)
    monkeypatch.delenv("SWMT_WORKSHOP_PATH", raising=False)
    s = Settings()
    assert s.base_game_path is None
    assert s.workshop_path is None


def test_blank_game_path_is_unset(monkeypatch):
    monkeypatch.setenv("SWMT_WORKSHOP_PATH", "  ")
    assert Settings().workshop_path is None
