"""Tests for the importlib-based helper_scripts loader."""

from pathlib import Path

import pytest

from backend.games.total_war_warhammer_3.registry.loader import (
    HelperScriptsNotConfiguredError,
    RegistryConstantNotFoundError,
    RegistryFileMissingError,
    RegistryFileSyntaxError,
    _derive_workshop_id,
    load_supported_effects,
    load_supported_effects_categories,
    load_supported_mods,
    supported_mods_source_path,
)

FIXTURES = Path(__file__).parent / "fixtures" / "helper_scripts"


def test_load_supported_mods_returns_list_of_dicts():
    mods = load_supported_mods(FIXTURES)
    assert isinstance(mods, list)
    assert len(mods) == 2
    assert mods[0]["name"] == "Test Mod A"


def test_load_supported_effects_returns_dict():
    effects = load_supported_effects(FIXTURES)
    assert isinstance(effects, dict)
    assert "infantry" in effects
    assert effects["cavalry"]["empire"] == ["bundle_c"]


def test_load_raises_when_path_unset(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(HelperScriptsNotConfiguredError):
        load_supported_mods(nonexistent)


def test_load_raises_when_file_missing(tmp_path):
    # tmp_path exists but has no supported_mods.py
    with pytest.raises(RegistryFileMissingError):
        load_supported_mods(tmp_path)


def test_load_raises_on_syntax_error():
    # The fixtures dir has _test_syntax_error.py; we point the loader at a
    # custom filename via the internal helper to test syntax-error handling.
    from backend.games.total_war_warhammer_3.registry.loader import _load_constant

    with pytest.raises(RegistryFileSyntaxError):
        _load_constant(FIXTURES, "_test_syntax_error.py", "SUPPORTED_MODS")


def test_load_raises_when_constant_missing():
    from backend.games.total_war_warhammer_3.registry.loader import _load_constant

    with pytest.raises(RegistryConstantNotFoundError):
        _load_constant(FIXTURES, "missing_constant.py", "SUPPORTED_MODS")


def test_load_resolves_sibling_imports():
    """The real `supported_mods.py` imports `from utilities import STEAM_LIBRARY_DRIVE`,
    so the loader must put `helper_scripts_path` on `sys.path` for the duration of
    the import. This test exercises that contract via fixture files."""
    import sys

    from backend.games.total_war_warhammer_3.registry.loader import _load_constant

    before = list(sys.path)
    result = _load_constant(FIXTURES, "with_sibling_constant.py", "WITH_SIBLING")
    after = list(sys.path)

    assert result == [{"name": "uses sibling", "value": "loaded-from-sibling"}]
    # `sys.path` must be restored to its pre-call state.
    assert before == after


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# _derive_workshop_id


def test_derive_workshop_id_returns_id_when_grandparent_is_appid():
    path = r"F:\SteamLibrary\steamapps\workshop\content\1142710\3513364573\dynamic_rors_compat.pack"
    assert _derive_workshop_id(path) == "3513364573"


def test_derive_workshop_id_returns_none_when_grandparent_is_not_appid():
    path = r"C:\some\other\folder\3513364573\dynamic_rors_compat.pack"
    assert _derive_workshop_id(path) is None


def test_derive_workshop_id_returns_none_for_empty_path():
    assert _derive_workshop_id("") is None
    assert _derive_workshop_id(None) is None


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# load_supported_effects_categories + supported_mods_source_path


def test_load_supported_effects_categories_returns_top_level_keys(tmp_path):
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    (helper / "data").mkdir()
    (helper / "data" / "dynamic_rors_effects.py").write_text('SUPPORTED_EFFECTS = {"melee_attack": {"id": 1}, "missile_damage": {"id": 2}}\n')
    cats = load_supported_effects_categories(helper)
    assert sorted(cats) == ["melee_attack", "missile_damage"]


def test_supported_mods_source_path_returns_expected_filename(tmp_path):
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    assert supported_mods_source_path(helper) == helper / "data" / "supported_mods.py"


def test_load_supported_mods_reads_the_reorganized_layout(tmp_path):
    """The registry lives in `data/` and imports `core.utilities`, as in the reorganized helper_scripts repo."""
    helper = tmp_path / "helper_scripts"
    (helper / "core").mkdir(parents=True)
    (helper / "data").mkdir()
    (helper / "core" / "__init__.py").write_text("")
    (helper / "core" / "utilities.py").write_text('STEAM_LIBRARY_DRIVE = "F:"\n')
    (helper / "data" / "__init__.py").write_text("")
    (helper / "data" / "supported_mods.py").write_text(
        'from core.utilities import STEAM_LIBRARY_DRIVE\n\nSUPPORTED_MODS = [{"name": "Layout Mod", "package_name": "layout", "path": STEAM_LIBRARY_DRIVE + "/x.pack"}]\n'
    )
    mods = load_supported_mods(helper)
    assert [m["name"] for m in mods] == ["Layout Mod"]
    assert mods[0]["path"] == "F:/x.pack"


def test_missing_registry_error_names_the_data_folder(tmp_path):
    """A helper_scripts folder without `data/supported_mods.py` reports that exact path."""
    with pytest.raises(RegistryFileMissingError) as exc:
        load_supported_mods(tmp_path)
    assert str(exc.value) == str(tmp_path / "data" / "supported_mods.py")
