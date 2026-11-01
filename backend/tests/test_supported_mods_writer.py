"""Tests for the libcst-based SUPPORTED_MODS writer."""

from __future__ import annotations

import pytest

from backend.games.total_war_warhammer_3.supported_mods_writer import (
    DuplicatePackageError,
    EntryNotFoundError,
    add_entry,
    remove_entry,
    update_entry,
)

_BASE_SOURCE = """from utilities import STEAM_LIBRARY_DRIVE

SUPPORTED_MODS = [
    {
        "name": "Vanilla",
        "package_name": "vanilla",
        "path": "",
        "modified_attributes": [],
    },
]
"""


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# add_entry


def test_add_entry_appends_new_workshop_mod():
    entry = {
        "name": "My Mod",
        "package_name": "my_mod.pack",
        "workshop_id": "1234567890",
        "modified_attributes": ["melee_attack"],
    }
    result = add_entry(_BASE_SOURCE, entry)

    # The new entry should appear in the list and the path should be the f-string form.
    assert '"name": "My Mod"' in result
    assert '"package_name": "my_mod.pack"' in result
    assert 'f"{STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710/1234567890/my_mod.pack"' in result
    assert '"modified_attributes": ["melee_attack"]' in result


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# update_entry


_TWO_ENTRY_SOURCE = """from utilities import STEAM_LIBRARY_DRIVE

SUPPORTED_MODS = [
    {
        "name": "Vanilla",
        "package_name": "vanilla",
        "path": "",
        "modified_attributes": [],
    },
    {
        "name": "Old Name",
        "package_name": "old_mod.pack",
        "path": f"{STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710/111/old_mod.pack",
        "modified_attributes": ["melee_attack"],
    },
]
"""


def test_update_entry_replaces_existing_by_package_name():
    new_entry = {
        "name": "New Name",
        "package_name": "old_mod.pack",
        "workshop_id": "222",
        "modified_attributes": ["ranged_damage"],
    }
    result = update_entry(_TWO_ENTRY_SOURCE, "old_mod.pack", new_entry)

    assert '"name": "New Name"' in result
    assert '"name": "Old Name"' not in result
    assert 'f"{STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710/222/old_mod.pack"' in result
    # Other entries untouched.
    assert '"name": "Vanilla"' in result


def test_update_entry_raises_when_package_not_found():
    with pytest.raises(EntryNotFoundError):
        update_entry(_TWO_ENTRY_SOURCE, "does_not_exist.pack", {"name": "x", "package_name": "does_not_exist.pack", "modified_attributes": []})


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# remove_entry


def test_remove_entry_drops_target_and_keeps_others():
    result = remove_entry(_TWO_ENTRY_SOURCE, "old_mod.pack")
    assert '"package_name": "old_mod.pack"' not in result
    assert '"package_name": "vanilla"' in result


def test_remove_entry_raises_when_package_not_found():
    with pytest.raises(EntryNotFoundError):
        remove_entry(_TWO_ENTRY_SOURCE, "does_not_exist.pack")


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# add_entry edge cases


def test_add_entry_raises_on_duplicate_package_name():
    entry = {"name": "Dup", "package_name": "vanilla", "modified_attributes": []}
    with pytest.raises(DuplicatePackageError):
        add_entry(_BASE_SOURCE, entry)


def test_add_entry_emits_plain_string_for_custom_path():
    entry = {
        "name": "Special",
        "package_name": "special.pack",
        "custom_path": True,
        "path": "/absolute/custom/path/special.pack",
        "modified_attributes": [],
    }
    result = add_entry(_BASE_SOURCE, entry)
    assert '"path": "/absolute/custom/path/special.pack"' in result
    # No f-string for this entry.
    assert "STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710//special.pack" not in result


def test_add_entry_serializes_pattern_overrides_and_character_overrides():
    entry = {
        "name": "Complex",
        "package_name": "complex.pack",
        "workshop_id": "999",
        "modified_attributes": [],
        "pattern_overrides": {"*": "vmp"},
        "character_overrides": {
            "vmp": {
                "allowed_lords": [{"land_unit": "wh_main_vmp_lord", "agent_subtype": "vmp_lord_x"}],
                "allowed_heroes": [],
            }
        },
        "ignore_generation": True,
    }
    result = add_entry(_BASE_SOURCE, entry)
    assert '"pattern_overrides": {"*": "vmp"}' in result
    assert '"allowed_lords": [{"land_unit": "wh_main_vmp_lord", "agent_subtype": "vmp_lord_x"}]' in result
    assert '"allowed_heroes": []' in result
    assert '"ignore_generation": True' in result


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Comment preservation


def test_writer_preserves_module_level_comments():
    source = """# Top of file comment.
from utilities import STEAM_LIBRARY_DRIVE

# Above the list.
SUPPORTED_MODS = [
    {
        "name": "Vanilla",
        "package_name": "vanilla",
        "path": "",
        "modified_attributes": [],
    },
]

# After the list.
"""
    result = add_entry(source, {"name": "New", "package_name": "new.pack", "workshop_id": "1", "modified_attributes": []})
    assert "# Top of file comment." in result
    assert "# Above the list." in result
    assert "# After the list." in result
