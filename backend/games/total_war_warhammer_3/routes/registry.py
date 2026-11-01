"""HTTP routes for the TW3 read-only registries."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.json_store import write_text_atomic
from backend.games.total_war_warhammer_3.helper_scripts_loader import (
    HelperScriptsLoaderError,
    HelperScriptsNotConfiguredError,
    RegistryFileMissingError,
    load_supported_effects_categories,
    load_supported_mods,
    supported_mods_source_path,
)
from backend.games.total_war_warhammer_3.routes._paths import helper_scripts_path
from backend.games.total_war_warhammer_3.supported_mods_writer import (
    DuplicatePackageError,
    EntryNotFoundError,
    add_entry,
    remove_entry,
    update_entry,
)

router = APIRouter()


@router.get("/supported-mods")
def get_supported_mods():
    """Return SUPPORTED_MODS from the configured helper_scripts directory.

    Returns:
        `{"mods": [...]}`.
    """
    try:
        mods = load_supported_mods(helper_scripts_path())
    except (HelperScriptsNotConfiguredError, RegistryFileMissingError) as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except HelperScriptsLoaderError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"mods": mods}


class SupportedModBody(BaseModel):
    """Request body for POST/PUT mutations on SUPPORTED_MODS."""

    entry: dict


def _write_and_reload(new_source: str) -> list[dict]:
    """Back up, write and reload the SUPPORTED_MODS source file.

    Args:
        new_source: Mutated `supported_mods.py` text.

    Returns:
        Freshly loaded mods.
    """
    source_path = supported_mods_source_path(helper_scripts_path())
    if not source_path.is_file():
        raise HTTPException(status_code=503, detail="data/supported_mods.py not found")
    backup = source_path.with_suffix(".py.bak")
    shutil.copyfile(source_path, backup)
    write_text_atomic(source_path, new_source)
    try:
        return load_supported_mods(helper_scripts_path())
    except HelperScriptsLoaderError as exc:
        shutil.copyfile(backup, source_path)
        raise HTTPException(status_code=500, detail=f"Write reloaded with error, restored from .bak: {exc}")


@router.post("/supported-mods")
def post_supported_mods(body: SupportedModBody):
    """Add a new entry to SUPPORTED_MODS and persist it.

    Args:
        body: Wrapper with the new entry.

    Returns:
        `{"mods": [...]}`, the reloaded list.
    """
    try:
        source_path = supported_mods_source_path(helper_scripts_path())
        if not source_path.is_file():
            raise HTTPException(status_code=503, detail="data/supported_mods.py not found")
        new_source = add_entry(source_path.read_text(encoding="utf-8"), body.entry)
    except HelperScriptsNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except DuplicatePackageError as exc:
        raise HTTPException(status_code=409, detail=f"Package already exists: {exc}")
    return {"mods": _write_and_reload(new_source)}


@router.put("/supported-mods/{package_name}")
def put_supported_mods(package_name: str, body: SupportedModBody):
    """Replace the SUPPORTED_MODS entry keyed by `package_name`.

    Args:
        package_name: Package name of the entry to replace.
        body: Wrapper with the replacement entry.

    Returns:
        `{"mods": [...]}`, the reloaded list.
    """
    try:
        source_path = supported_mods_source_path(helper_scripts_path())
        if not source_path.is_file():
            raise HTTPException(status_code=503, detail="data/supported_mods.py not found")
        new_source = update_entry(source_path.read_text(encoding="utf-8"), package_name, body.entry)
    except HelperScriptsNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except EntryNotFoundError:
        raise HTTPException(status_code=404, detail=f"Mod not found: {package_name}")
    return {"mods": _write_and_reload(new_source)}


@router.delete("/supported-mods/{package_name}")
def delete_supported_mods(package_name: str):
    """Remove the SUPPORTED_MODS entry keyed by `package_name`.

    Args:
        package_name: Package name of the entry to remove.

    Returns:
        `{"mods": [...]}`, the reloaded list.
    """
    try:
        source_path = supported_mods_source_path(helper_scripts_path())
        if not source_path.is_file():
            raise HTTPException(status_code=503, detail="data/supported_mods.py not found")
        new_source = remove_entry(source_path.read_text(encoding="utf-8"), package_name)
    except HelperScriptsNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except EntryNotFoundError:
        raise HTTPException(status_code=404, detail=f"Mod not found: {package_name}")
    return {"mods": _write_and_reload(new_source)}


@router.get("/supported-effects")
def get_supported_effects():
    """Return the top-level keys of `SUPPORTED_EFFECTS` for the Modified Attributes autocomplete.

    Returns:
        `{"categories": [...]}`.
    """
    try:
        categories = load_supported_effects_categories(helper_scripts_path())
    except (HelperScriptsNotConfiguredError, RegistryFileMissingError) as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except HelperScriptsLoaderError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"categories": categories}
