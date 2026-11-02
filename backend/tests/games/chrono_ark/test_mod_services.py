"""Chrono Ark mod services: export into the mod, the detail view and reset."""

import json
from pathlib import Path

import pytest
from backend.core.errors import DomainError
from backend.core.paths import GameStorage
from backend.data.translation_store import load_translations, save_translations_bulk
from backend.games.base import ModInfo
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.chrono_ark.services import mods as mod_services

MOD_ID = "900000004"
CSV_HEADER = "Key,Type,Desc,Korean,English,Japanese,Chinese,Chinese-TW [zh-tw]\n"
ORIGINAL_CSV = CSV_HEADER + "Buff/B_1_Name,Text,,테스트,,,,\n"


@pytest.fixture
def mod_dir(tmp_path: Path, monkeypatch) -> Path:
    """A one-string CSV mod that the adapter finds by `MOD_ID`, with no Harmony injector installed.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The mod's folder.
    """
    path = tmp_path / "workshop" / MOD_ID
    (path / "Localization").mkdir(parents=True)
    (path / "Localization" / "LangDataDB.csv").write_text(ORIGINAL_CSV, encoding="utf-8")
    mod = ModInfo(mod_id=MOD_ID, name="Fake Mod", author="Tester", path=path)
    monkeypatch.setattr(ChronoArkAdapter, "find_mod", lambda self, mod_id, search_path=None: mod if mod_id == MOD_ID else None)
    monkeypatch.setattr(ChronoArkAdapter, "get_translation_overrides_dir", lambda self: None)
    return path


def _csv(mod_dir: Path) -> str:
    return (mod_dir / "Localization" / "LangDataDB.csv").read_text(encoding="utf-8-sig")


def test_export_writes_the_csv_and_reset_restores_it(mod_dir: Path):
    save_translations_bulk(MOD_ID, {"Buff/B_1_Name": "Test"}, game_id=GAME_ID)

    result = mod_services.export_mod(MOD_ID)

    assert (result["applied"], result["files_written"]) == (1, ["LangDataDB.csv"])
    assert "Test" in _csv(mod_dir)
    [row] = mod_services.mod_detail(MOD_ID)["strings"]
    assert (row["english"], row["is_synced"], row["original_english"]) == ("Test", True, "")

    reset = mod_services.reset_mod(MOD_ID)

    assert (reset["csv_restored"], reset["overrides_cleared"]) == (True, False)
    assert _csv(mod_dir).replace("\r\n", "\n") == ORIGINAL_CSV
    assert load_translations(MOD_ID, game_id=GAME_ID) == {}
    assert not (GameStorage(GAME_ID).mod_dir(MOD_ID) / "original_csvs").exists()


def test_export_refuses_a_mod_with_no_translations(mod_dir: Path):
    with pytest.raises(DomainError, match="No translations"):
        mod_services.export_mod(MOD_ID)


def test_export_and_reset_only_touch_this_mods_override_block(mod_dir: Path, tmp_path: Path, monkeypatch):
    overrides_dir = tmp_path / "ModTranslationInjector"
    overrides_dir.mkdir()
    (overrides_dir / "keyed_overrides.json").write_text(json.dumps({"Other Mod": {"k": "v"}}), encoding="utf-8")
    monkeypatch.setattr(ChronoArkAdapter, "get_translation_overrides_dir", lambda self: overrides_dir)
    save_translations_bulk(MOD_ID, {"Buff/B_1_Name": "Test"}, game_id=GAME_ID)

    result = mod_services.export_mod(MOD_ID)

    assert (result["keyed_overrides_written"], result["files_written"]) == (1, [])
    assert json.loads((overrides_dir / "keyed_overrides.json").read_text(encoding="utf-8")) == {"Other Mod": {"k": "v"}, "Fake Mod": {"Buff/B_1_Name": "Test"}}
    # The mod's own CSV is left alone when the injector carries the translations.
    assert _csv(mod_dir) == ORIGINAL_CSV

    assert mod_services.reset_mod(MOD_ID)["overrides_cleared"] is True
    assert json.loads((overrides_dir / "keyed_overrides.json").read_text(encoding="utf-8")) == {"Other Mod": {"k": "v"}}
