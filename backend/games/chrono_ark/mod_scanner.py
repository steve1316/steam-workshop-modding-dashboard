"""Mod scanner: discovers Chrono Ark workshop mods and what localization resources each has."""

import json
from pathlib import Path
from backend.games.base import ModInfo
from backend.games.chrono_ark.csv_extractor import extract_mod_strings


def _read_mod_metadata(mod_path: Path, metadata_filename: str) -> dict:
    """Read the mod's metadata JSON.

    Args:
        mod_path: Mod root directory.
        metadata_filename: Metadata JSON filename.

    Returns:
        Metadata fields, or `{}` if missing or unreadable.
    """
    json_path = mod_path / metadata_filename
    if not json_path.exists():
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def classify_mod(
    mod_path: Path,
    metadata_filename: str,
    skip_dlls: set[str],
) -> ModInfo:
    """Determine a mod's localization resources (CSVs, DLLs) and whether English is already populated.

    Args:
        mod_path: Mod root directory.
        metadata_filename: Metadata JSON filename.
        skip_dlls: DLL filenames to skip.

    Returns:
        Discovered `ModInfo`.
    """
    mod_id = mod_path.name
    metadata = _read_mod_metadata(mod_path, metadata_filename)

    info = ModInfo(
        mod_id=mod_id,
        name=metadata.get("id", metadata.get("name", mod_id)),
        author=metadata.get("Uploader", metadata.get("author", "")),
        path=mod_path,
    )

    loc_dir = mod_path / "Localization"
    if loc_dir.exists():
        for csv_file in loc_dir.glob("*.csv"):
            info.loc_file_paths.append(csv_file)

    for csv_file in mod_path.glob("Lang*.csv"):
        if csv_file not in info.loc_file_paths:
            info.loc_file_paths.append(csv_file)

    info.has_loc_files = len(info.loc_file_paths) > 0

    assemblies_dir = mod_path / "Assemblies"
    if assemblies_dir.exists():
        for dll_file in assemblies_dir.glob("*.dll"):
            if dll_file.name not in skip_dlls:
                info.dll_paths.append(dll_file)

    info.has_dll = len(info.dll_paths) > 0

    if info.has_loc_files:
        strings, _ = extract_mod_strings(mod_path)
        info.entry_count = len(strings)

        english_count = sum(1 for s in strings.values() if s.translations.get("English", "").strip())
        info.target_lang_populated = english_count > 0

    return info


def scan_workshop(
    workshop_path: Path,
    metadata_filename: str,
    skip_dlls: set[str],
    ignored_ids: set[str] | None = None,
) -> list[ModInfo]:
    """Scan the workshop directory for installed mods.

    Args:
        workshop_path: Workshop content directory.
        metadata_filename: Metadata JSON filename.
        skip_dlls: DLL filenames to skip.
        ignored_ids: Mod ids to skip entirely.

    Returns:
        `ModInfo` per mod, sorted by mod_id.
    """
    if not workshop_path.exists():
        print(f"Workshop path not found: {workshop_path}")
        return []

    skip = ignored_ids or set()
    mods = []
    for mod_dir in sorted(workshop_path.iterdir()):
        if mod_dir.is_dir() and mod_dir.name not in skip:
            info = classify_mod(mod_dir, metadata_filename, skip_dlls)
            mods.append(info)

    return mods
