"""
GDE (Game Data Editor) JSON extractor for Chrono Ark mods.

Parses the `gdata/Add/*.json` files that mods ship alongside their DLLs.
These files define skills, buffs, equipment, characters, etc. and contain
localizable text fields such as Name, Description, and dialogue arrays.
"""

import json
from pathlib import Path
from backend.models import LocString
from backend.text_utils import has_cjk as _has_cjk
from backend.core.json_store import write_json


# Maps (schema, field_name) to a canonical suffix used in the localization key.
# For example Skill with field "Name" → key suffix "_Name".
_FIELD_SUFFIXES: dict[str, str] = {
    "Name": "_Name",
    "name": "_Name",
    "Description": "_Description",
    "Desc": "_Description",
    "Des": "_Description",
    "PassiveName": "_PassiveName",
    "PassiveDes": "_PassiveDesc",
    "SelectInfo": "_SelectInfo",
    "Flavor": "_Flavor",
    "SkinName": "_SkinName",
    "SkinDesc": "_SkinDesc",
    "UnlockString": "_UnlockString",
    "CampSelectWord": "_CampSelectWord",
    "Text_MasterTarget": "_Text_MasterTarget",
}

# Schema names used as key prefixes (matches base-game CSV convention).
_SCHEMA_PREFIX: dict[str, str] = {
    "Skill": "Skill",
    "Buff": "Buff",
    "Item_Equip": "Item_Equip",
    "Item_Passive": "Item_Passive",
    "Character": "Character",
    "Character_Skin": "Character_Skin",
    "SkillExtended": "SkillExtended",
    "SkillKeyword": "SkillKeyword",
    "SimpleCampDialogue": "SimpleCampDialogue",
    "Item_Consume": "Item_Consume",
    "Item_Active": "Item_Active",
    "Item_Scroll": "Item_Scroll",
    "Item_Misc": "Item_Misc",
    "Item_Potions": "Item_Potions",
    "Item_Friendship": "Item_Friendship",
    "Enemy": "Enemy",
    "RandomEvent": "RandomEvent",
    "CurseList": "CurseList",
    "EnchantList": "EnchantList",
    "SpecialKey": "SpecialKey",
    "SpecialRule": "SpecialRule",
    "UnlockWindow": "UnlockWindow",
    "ArkUpgrade": "ArkUpgrade",
}

# Character fields that hold string arrays (dialogue lines).
_DIALOGUE_ARRAY_FIELDS = {
    "Text_Battle_Idle",
    "Text_Battle_ND",
    "Text_Battle_AllyND",
    "Text_Battle_Start",
    "Text_Battle_Kill",
    "Text_Battle_Cri",
    "Text_Battle_Healed",
    "Text_Field_Idle",
    "Text_Field_GetItem",
    "Text_Field_Potion_N",
    "Text_Field_Potion_P",
    "Text_PharosLeader",
    "Text_Ex",
    "Text_EquipGet",
    "Text_BangBangKaBang",
    "Dialogues",
}


def _extract_gdata_file(file_path: Path) -> dict[str, LocString]:
    """Extract localization entries from a single gdata JSON file.

    Parses the JSON structure for known schemas (Skill, Buff, Item, etc.)
    and extracts scalar text fields and dialogue string arrays that
    contain CJK text.

    Args:
        file_path: Path to the gdata JSON file.

    Returns:
        Dictionary mapping localization key to LocString. Returns an
        empty dict if the file cannot be read or contains no localizable
        entries.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Warning: Could not read {file_path.name}: {e}")
        return {}

    results: dict[str, LocString] = {}

    for item_id, obj in data.items():
        if not isinstance(obj, dict):
            continue

        schema = obj.get("_gdeSchema", "")
        prefix = _SCHEMA_PREFIX.get(schema, schema)

        # Extract scalar text fields (Name, Description, etc.).
        for field_name, suffix in _FIELD_SUFFIXES.items():
            value = obj.get(field_name)
            if not value or not isinstance(value, str):
                continue

            loc_key = f"{prefix}/{item_id}{suffix}"
            lang = "Chinese" if _has_cjk(value) else "English"
            results[loc_key] = LocString(
                key=loc_key,
                type="Text",
                desc="",
                translations={lang: value},
                source_file=file_path.name,
            )

        # Extract dialogue string arrays (Text_Battle_Idle, etc.).
        for field_name in _DIALOGUE_ARRAY_FIELDS:
            arr = obj.get(field_name)
            if not arr:
                continue

            if isinstance(arr, list):
                for idx, line in enumerate(arr):
                    if not isinstance(line, str) or not line.strip():
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    loc_key = f"{prefix}/{item_id}_{field_name}_{idx}"
                    lang = "Chinese" if _has_cjk(line) else "English"
                    results[loc_key] = LocString(
                        key=loc_key,
                        type="Text",
                        desc="",
                        translations={lang: line},
                        source_file=file_path.name,
                    )
            elif isinstance(arr, str) and arr.strip():
                # Some dialogue fields might be a single string.
                loc_key = f"{prefix}/{item_id}_{field_name}"
                text = arr.strip()
                lang = "Chinese" if _has_cjk(text) else "English"
                results[loc_key] = LocString(
                    key=loc_key,
                    type="Text",
                    desc="",
                    translations={lang: text},
                    source_file=file_path.name,
                )

    return results


def export_gdata_translations(
    mod_path: Path,
    translations: dict[str, str],
) -> list[str]:
    """Write English translations back into a mod's gdata JSON files.

    Iterates over each JSON object in `gdata/Add/*.json`, mirrors the
    extraction key logic, and overwrites the source-language field with
    the English translation when one exists.

    Args:
        mod_path: Root directory of the mod.
        translations: Mapping of localization key to English text.

    Returns:
        List of JSON filenames that were modified.
    """
    gdata_dir = mod_path / "gdata" / "Add"
    if not gdata_dir.exists():
        return []

    json_files = sorted(gdata_dir.glob("*.json"))
    if not json_files:
        return []

    files_modified: list[str] = []

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        modified = False

        for item_id, obj in data.items():
            if not isinstance(obj, dict):
                continue

            schema = obj.get("_gdeSchema", "")
            prefix = _SCHEMA_PREFIX.get(schema, schema)

            # Update scalar text fields.
            for field_name, suffix in _FIELD_SUFFIXES.items():
                if field_name not in obj:
                    continue
                loc_key = f"{prefix}/{item_id}{suffix}"
                if loc_key in translations:
                    obj[field_name] = translations[loc_key]
                    modified = True

            # Update dialogue string arrays.
            for field_name in _DIALOGUE_ARRAY_FIELDS:
                arr = obj.get(field_name)
                if not arr:
                    continue

                if isinstance(arr, list):
                    for idx in range(len(arr)):
                        loc_key = f"{prefix}/{item_id}_{field_name}_{idx}"
                        if loc_key in translations:
                            arr[idx] = translations[loc_key]
                            modified = True
                elif isinstance(arr, str):
                    loc_key = f"{prefix}/{item_id}_{field_name}"
                    if loc_key in translations:
                        obj[field_name] = translations[loc_key]
                        modified = True

        if modified:
            write_json(json_file, data)
            files_modified.append(json_file.name)

    return files_modified


def extract_mod_gdata_strings(mod_path: Path) -> dict[str, LocString]:
    """
    Extract all localization strings from a mod's `gdata/Add/` directory.

    Args:
        mod_path: Root directory of the mod.

    Returns:
        Dictionary mapping localization key to LocString.
    """
    gdata_dir = mod_path / "gdata" / "Add"
    if not gdata_dir.exists():
        return {}

    all_strings: dict[str, LocString] = {}

    json_files = sorted(gdata_dir.glob("*.json"))
    if not json_files:
        return {}

    for json_file in json_files:
        entries = _extract_gdata_file(json_file)
        all_strings.update(entries)

    if all_strings:
        print(f"  Extracted {len(all_strings)} entries from {len(json_files)} gdata files")

    return all_strings
