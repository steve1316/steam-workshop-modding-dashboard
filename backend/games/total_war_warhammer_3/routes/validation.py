"""HTTP route for the TW3 FK validation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.games.total_war_warhammer_3.paths import helper_scripts_path
from backend.games.total_war_warhammer_3.registry.loader import (
    HelperScriptsLoaderError,
    HelperScriptsNotConfiguredError,
    RegistryFileMissingError,
    load_supported_effects,
    load_supported_mods,
)
from backend.games.total_war_warhammer_3.registry.validator import validate_registries

router = APIRouter()


@router.get("/validation")
def get_validation():
    """Run FK validation against the configured mod and effects registries.

    Returns:
        `{"issues": [...]}`, empty when none are found.
    """
    try:
        mods = load_supported_mods(helper_scripts_path())
        effects = load_supported_effects(helper_scripts_path())
    except (HelperScriptsNotConfiguredError, RegistryFileMissingError) as exc:
        raise HTTPException(status_code=503, detail=f"Registry unavailable: {exc}") from exc
    except HelperScriptsLoaderError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"issues": validate_registries(mods, effects)}
