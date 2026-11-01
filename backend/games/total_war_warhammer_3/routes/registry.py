"""HTTP routes for the TW3 read-only registries."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
from backend.core.json_store import write_text_atomic

router = APIRouter()


@router.get("/supported-mods")
def get_supported_mods():
    """Return SUPPORTED_MODS from the configured helper_scripts directory.

    Returns:
        `{"mods": [...]}` on success.

    Raises:
        HTTPException(503): When helper_scripts_path is unset or the file is missing.
        HTTPException(500): When the file fails to load (syntax error, missing constant).
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
    """Backup, write, and reload the SUPPORTED_MODS source file.

    Args:
        new_source: The mutated `supported_mods.py` text to persist.

    Returns:
        The freshly loaded list of mods.

    Raises:
        HTTPException(500): When the post-write reload fails (after restoring backup).
        HTTPException(503): When helper_scripts_path is unset.
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
    """Add a new entry to SUPPORTED_MODS and persist to disk.

    Args:
        body: Wrapper containing the new entry payload.

    Returns:
        `{"mods": [...]}` - the freshly loaded list.

    Raises:
        HTTPException(409): When `package_name` is already present.
        HTTPException(503): When helper_scripts is unset or missing.
        HTTPException(500): When the file fails to parse or write.
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
    """Replace an existing SUPPORTED_MODS entry, keyed by `package_name`.

    Args:
        package_name: Package name of the entry to replace.
        body: Wrapper containing the replacement entry payload.

    Returns:
        `{"mods": [...]}` - the freshly loaded list.

    Raises:
        HTTPException(404): When no entry with `package_name` exists.
        HTTPException(503): When helper_scripts is unset or missing.
        HTTPException(500): When the file fails to parse or write.
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
    """Remove an existing SUPPORTED_MODS entry, keyed by `package_name`.

    Args:
        package_name: Package name of the entry to remove.

    Returns:
        `{"mods": [...]}` - the freshly loaded list.

    Raises:
        HTTPException(404): When no entry with `package_name` exists.
        HTTPException(503): When helper_scripts is unset or missing.
        HTTPException(500): When the file fails to parse or write.
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
    """Return the top-level keys of `SUPPORTED_EFFECTS`.

    Used by the Supported Mods CRUD form's Modified Attributes autocomplete.

    Returns:
        `{"categories": [...]}` on success.

    Raises:
        HTTPException(503): When helper_scripts_path is unset or the file is missing.
        HTTPException(500): When the file fails to load.
    """
    try:
        categories = load_supported_effects_categories(helper_scripts_path())
    except (HelperScriptsNotConfiguredError, RegistryFileMissingError) as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}")
    except HelperScriptsLoaderError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"categories": categories}
