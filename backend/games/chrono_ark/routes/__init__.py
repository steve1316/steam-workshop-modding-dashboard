"""HTTP routers owned by the Chrono Ark adapter."""

from fastapi import APIRouter

from backend.games.chrono_ark.routes import mods, translation, glossary


def build_chrono_ark_router() -> APIRouter:
    """Compose the mods/translation/glossary sub-routers under `/api/games/chrono_ark`.

    Returns:
        Composed `APIRouter`.
    """
    composed = APIRouter(prefix="/api/games/chrono_ark")
    composed.include_router(mods.router)
    composed.include_router(translation.router)
    composed.include_router(glossary.router)
    return composed
