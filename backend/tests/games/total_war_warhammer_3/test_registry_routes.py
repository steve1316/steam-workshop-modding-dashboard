"""Tests for the TW3 registry routes."""

from fastapi.testclient import TestClient

from backend.app import app

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# POST /supported-mods


_FIXTURE_SOURCE = """from core.utilities import STEAM_LIBRARY_DRIVE

SUPPORTED_MODS = [
    {
        "name": "Vanilla",
        "package_name": "vanilla",
        "path": "",
        "modified_attributes": [],
    },
]
"""


def _write_layout(helper):
    """Create the reorganized helper_scripts package folders: `core/` with `utilities.py`, and an empty `data/`.

    Args:
        helper: The helper_scripts directory to populate.
    """
    (helper / "core").mkdir()
    (helper / "data").mkdir()
    (helper / "core" / "__init__.py").write_text("")
    (helper / "core" / "utilities.py").write_text('STEAM_LIBRARY_DRIVE = "F:"\n')
    (helper / "data" / "__init__.py").write_text("")


def _setup_helper(monkeypatch, tmp_path):
    """Create a minimal helper_scripts directory and point config at it.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        tmp_path: pytest tmp_path fixture.

    Returns:
        The created helper_scripts `Path`.
    """
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    _write_layout(helper)
    (helper / "data" / "supported_mods.py").write_text(_FIXTURE_SOURCE)
    monkeypatch.setattr("backend.core.settings.settings.tw3.helper_path", str(helper))
    return helper


def test_post_supported_mods_adds_new_entry(monkeypatch, tmp_path):
    """POST with a new package_name returns 200 and the mod appears in the list."""
    _setup_helper(monkeypatch, tmp_path)
    body = {
        "entry": {
            "name": "New Mod",
            "package_name": "new.pack",
            "workshop_id": "1234567890",
            "modified_attributes": ["melee_attack"],
        }
    }
    res = TestClient(app).post("/api/games/total_war_warhammer_3/supported-mods", json=body)
    assert res.status_code == 200
    mods = res.json()["mods"]
    assert any(m["package_name"] == "new.pack" for m in mods)


def test_post_supported_mods_returns_409_on_duplicate(monkeypatch, tmp_path):
    """POST with an existing package_name returns 409 Conflict."""
    _setup_helper(monkeypatch, tmp_path)
    body = {"entry": {"name": "Dup", "package_name": "vanilla", "modified_attributes": []}}
    res = TestClient(app).post("/api/games/total_war_warhammer_3/supported-mods", json=body)
    assert res.status_code == 409


def test_post_supported_mods_returns_503_when_helper_path_unset(monkeypatch):
    """POST returns 503 when TW3_HELPER_PATH is not configured."""
    monkeypatch.setattr("backend.core.settings.settings.tw3.helper_path", "")
    body = {"entry": {"name": "X", "package_name": "x.pack", "modified_attributes": []}}
    res = TestClient(app).post("/api/games/total_war_warhammer_3/supported-mods", json=body)
    assert res.status_code == 503


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# PUT /supported-mods/{package_name}


_TWO_ENTRY_FIXTURE = """from core.utilities import STEAM_LIBRARY_DRIVE

SUPPORTED_MODS = [
    {
        "name": "Vanilla",
        "package_name": "vanilla",
        "path": "",
        "modified_attributes": [],
    },
    {
        "name": "Old Name",
        "package_name": "target.pack",
        "path": f"{STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710/111/target.pack",
        "modified_attributes": [],
    },
]
"""


def _setup_helper_with_two(monkeypatch, tmp_path):
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    _write_layout(helper)
    (helper / "data" / "supported_mods.py").write_text(_TWO_ENTRY_FIXTURE)
    monkeypatch.setattr("backend.core.settings.settings.tw3.helper_path", str(helper))
    return helper


def test_put_supported_mods_updates_existing_entry(monkeypatch, tmp_path):
    _setup_helper_with_two(monkeypatch, tmp_path)
    body = {
        "entry": {
            "name": "New Name",
            "package_name": "target.pack",
            "workshop_id": "222",
            "modified_attributes": ["ranged_damage"],
        }
    }
    res = TestClient(app).put("/api/games/total_war_warhammer_3/supported-mods/target.pack", json=body)
    assert res.status_code == 200
    mods = res.json()["mods"]
    target = next(m for m in mods if m["package_name"] == "target.pack")
    assert target["name"] == "New Name"


def test_put_supported_mods_returns_404_when_missing(monkeypatch, tmp_path):
    _setup_helper_with_two(monkeypatch, tmp_path)
    body = {"entry": {"name": "X", "package_name": "ghost.pack", "modified_attributes": []}}
    res = TestClient(app).put("/api/games/total_war_warhammer_3/supported-mods/ghost.pack", json=body)
    assert res.status_code == 404


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# DELETE /supported-mods/{package_name}


def test_delete_supported_mods_removes_entry(monkeypatch, tmp_path):
    _setup_helper_with_two(monkeypatch, tmp_path)
    res = TestClient(app).delete("/api/games/total_war_warhammer_3/supported-mods/target.pack")
    assert res.status_code == 200
    mods = res.json()["mods"]
    assert all(m["package_name"] != "target.pack" for m in mods)


def test_delete_supported_mods_returns_404_when_missing(monkeypatch, tmp_path):
    _setup_helper_with_two(monkeypatch, tmp_path)
    res = TestClient(app).delete("/api/games/total_war_warhammer_3/supported-mods/ghost.pack")
    assert res.status_code == 404


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# GET /supported-effects


def test_get_supported_effects_returns_top_level_keys(monkeypatch, tmp_path):
    helper = tmp_path / "helper_scripts"
    helper.mkdir()
    _write_layout(helper)
    (helper / "data" / "dynamic_rors_effects.py").write_text('SUPPORTED_EFFECTS = {"melee_attack": {"id": 1}, "missile_damage": {"id": 2}}\n')
    monkeypatch.setattr("backend.core.settings.settings.tw3.helper_path", str(helper))
    res = TestClient(app).get("/api/games/total_war_warhammer_3/supported-effects")
    assert res.status_code == 200
    assert sorted(res.json()["categories"]) == ["melee_attack", "missile_damage"]
