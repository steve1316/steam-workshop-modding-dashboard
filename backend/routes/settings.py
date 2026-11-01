"""Settings and stats API endpoints for the Steam Workshop Modding Dashboard."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend import config
from backend.data.progress_tracker import ProgressTracker
from backend.data.translation_memory import TranslationMemory
from backend.games.chrono_ark import GAME_ID
from backend.games.registry import list_games as registry_list_games
from backend.process_manager import is_managed
from backend.routes.helpers import _mask_key, _update_env_file, chrono_ark_adapter, current_adapter, set_active_game
from backend.routes.models import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/api")


@router.get("/game")
async def get_game_info():
    """Return metadata about the active game adapter.

    Returns:
        `game_id` and `game_name`.
    """
    return {
        "game_id": current_adapter().game_id,
        "game_name": current_adapter().game_name,
    }


@router.get("/games")
async def list_games():
    """Return chassis metadata for all registered game adapters.

    Returns:
        `{game_id, display_name, icon, capabilities}` dicts.
    """
    from backend.games.registry import list_games_metadata

    return list_games_metadata()


@router.get("/settings")
async def get_settings():
    """Return current settings with API keys masked.

    Returns:
        All configuration values.
    """
    return SettingsResponse(
        provider=config.TRANSLATION_PROVIDER,
        batch_size=config.BATCH_SIZE,
        anthropic_api_key_set=_mask_key(config.ANTHROPIC_API_KEY),
        openai_api_key_set=_mask_key(config.OPENAI_API_KEY),
        deepl_api_key_set=_mask_key(config.DEEPL_API_KEY),
        claude_model=config.CLAUDE_MODEL,
        openai_model=config.OPENAI_MODEL,
        ollama_base_url=config.OLLAMA_BASE_URL,
        ollama_model=config.OLLAMA_MODEL,
        ollama_vram_tier=config.OLLAMA_VRAM_TIER,
        ollama_status="unknown",
        llamacpp_base_url=config.LLAMACPP_BASE_URL,
        llamacpp_model=config.LLAMACPP_MODEL,
        llamacpp_binary_path=config.LLAMACPP_BINARY_PATH,
        llamacpp_model_path=config.LLAMACPP_MODEL_PATH,
        llamacpp_gpu_layers=config.LLAMACPP_GPU_LAYERS,
        llamacpp_ctx_size=config.LLAMACPP_CTX_SIZE,
        llamacpp_vram_tier=config.LLAMACPP_VRAM_TIER,
        ollama_managed=is_managed("ollama"),
        llamacpp_managed=is_managed("llamacpp"),
        ignored_mods=config.IGNORED_MODS,
        active_game=config.ACTIVE_GAME,
        tw3_helper_path=config.TW3_HELPER_PATH,
        tw3_rpfm_cli_path=config.TW3_RPFM_CLI_PATH,
        tw3_steam_library_drive=config.TW3_STEAM_LIBRARY_DRIVE,
        steamcmd_path=config.STEAMCMD_PATH,
        steam_username=config.STEAM_USERNAME,
        games={game_id: {} for game_id in registry_list_games()},
    )


@router.post("/settings")
async def update_settings(payload: SettingsUpdate):
    """Update any provided settings and persist them to .env."""
    env_updates: dict[str, str] = {}

    if payload.provider is not None:
        if payload.provider not in ("claude", "openai", "deepl", "ollama", "llamacpp", "manual"):
            raise HTTPException(400, f"Invalid provider: {payload.provider}")
        config.TRANSLATION_PROVIDER = payload.provider
        env_updates["SWMT_TRANSLATION_PROVIDER"] = payload.provider

    if payload.batch_size is not None:
        if payload.batch_size < 1:
            raise HTTPException(400, "Batch size must be >= 1")
        config.BATCH_SIZE = payload.batch_size
        env_updates["SWMT_BATCH_SIZE"] = str(payload.batch_size)

    if payload.anthropic_api_key is not None:
        config.ANTHROPIC_API_KEY = payload.anthropic_api_key
        env_updates["SWMT_ANTHROPIC_API_KEY"] = payload.anthropic_api_key

    if payload.openai_api_key is not None:
        config.OPENAI_API_KEY = payload.openai_api_key
        env_updates["SWMT_OPENAI_API_KEY"] = payload.openai_api_key

    if payload.deepl_api_key is not None:
        config.DEEPL_API_KEY = payload.deepl_api_key
        env_updates["SWMT_DEEPL_API_KEY"] = payload.deepl_api_key

    if payload.claude_model is not None:
        config.CLAUDE_MODEL = payload.claude_model
        env_updates["SWMT_CLAUDE_MODEL"] = payload.claude_model

    if payload.openai_model is not None:
        config.OPENAI_MODEL = payload.openai_model
        env_updates["SWMT_OPENAI_MODEL"] = payload.openai_model

    if payload.ollama_base_url is not None:
        config.OLLAMA_BASE_URL = payload.ollama_base_url
        env_updates["SWMT_OLLAMA_BASE_URL"] = payload.ollama_base_url

    if payload.ollama_model is not None:
        config.OLLAMA_MODEL = payload.ollama_model
        env_updates["SWMT_OLLAMA_MODEL"] = payload.ollama_model

    if payload.ollama_vram_tier is not None:
        config.OLLAMA_VRAM_TIER = payload.ollama_vram_tier
        env_updates["SWMT_OLLAMA_VRAM_TIER"] = payload.ollama_vram_tier

    if payload.llamacpp_base_url is not None:
        config.LLAMACPP_BASE_URL = payload.llamacpp_base_url
        env_updates["SWMT_LLAMACPP_BASE_URL"] = payload.llamacpp_base_url

    if payload.llamacpp_model is not None:
        config.LLAMACPP_MODEL = payload.llamacpp_model
        env_updates["SWMT_LLAMACPP_MODEL"] = payload.llamacpp_model

    if payload.llamacpp_binary_path is not None:
        config.LLAMACPP_BINARY_PATH = payload.llamacpp_binary_path
        env_updates["SWMT_LLAMACPP_BINARY_PATH"] = payload.llamacpp_binary_path

    if payload.llamacpp_model_path is not None:
        config.LLAMACPP_MODEL_PATH = payload.llamacpp_model_path
        env_updates["SWMT_LLAMACPP_MODEL_PATH"] = payload.llamacpp_model_path

    if payload.llamacpp_gpu_layers is not None:
        config.LLAMACPP_GPU_LAYERS = payload.llamacpp_gpu_layers
        env_updates["SWMT_LLAMACPP_GPU_LAYERS"] = str(payload.llamacpp_gpu_layers)

    if payload.llamacpp_ctx_size is not None:
        config.LLAMACPP_CTX_SIZE = payload.llamacpp_ctx_size
        env_updates["SWMT_LLAMACPP_CTX_SIZE"] = str(payload.llamacpp_ctx_size)

    if payload.llamacpp_vram_tier is not None:
        config.LLAMACPP_VRAM_TIER = payload.llamacpp_vram_tier
        env_updates["SWMT_LLAMACPP_VRAM_TIER"] = payload.llamacpp_vram_tier

    if payload.ignored_mods is not None:
        config.IGNORED_MODS = payload.ignored_mods
        env_updates["SWMT_IGNORED_MODS"] = ",".join(payload.ignored_mods)

    if payload.active_game is not None:
        try:
            set_active_game(payload.active_game)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        env_updates["SWMT_ACTIVE_GAME"] = payload.active_game

    if payload.tw3_helper_path is not None:
        config.TW3_HELPER_PATH = payload.tw3_helper_path
        env_updates["SWMT_TW3_HELPER_PATH"] = payload.tw3_helper_path

    if payload.tw3_rpfm_cli_path is not None:
        config.TW3_RPFM_CLI_PATH = payload.tw3_rpfm_cli_path
        env_updates["SWMT_TW3_RPFM_CLI_PATH"] = payload.tw3_rpfm_cli_path

    if payload.tw3_steam_library_drive is not None:
        config.TW3_STEAM_LIBRARY_DRIVE = payload.tw3_steam_library_drive
        env_updates["SWMT_TW3_STEAM_LIBRARY_DRIVE"] = payload.tw3_steam_library_drive

    if payload.steamcmd_path is not None:
        config.STEAMCMD_PATH = payload.steamcmd_path
        env_updates["SWMT_STEAMCMD_PATH"] = payload.steamcmd_path

    if payload.steam_username is not None:
        config.STEAM_USERNAME = payload.steam_username
        env_updates["SWMT_STEAM_USERNAME"] = payload.steam_username

    if env_updates:
        _update_env_file(env_updates)

    return await get_settings()


@router.get("/models/{provider_id}")
async def get_provider_models(provider_id: str):
    """Return the available models and pricing for a given provider.

    Args:
        provider_id: `"claude"` or `"openai"`.

    Returns:
        `models` list with ID, label, and per-MTok pricing.
    """
    if provider_id == "claude":
        from backend.providers.claude_provider import CLAUDE_MODELS

        return JSONResponse({"models": [{"id": k, **v} for k, v in CLAUDE_MODELS.items()]})
    elif provider_id == "openai":
        from backend.providers.openai_provider import OPENAI_MODELS

        return JSONResponse({"models": [{"id": k, **v} for k, v in OPENAI_MODELS.items()]})
    raise HTTPException(404, f"No model catalog for provider: {provider_id}")


@router.get("/stats")
async def get_stats():
    """Get global statistics for translation memory and progress.

    Returns:
        `tm_entries`, `tm_hits` (session cache hits), `total_mods`, `global_progress` (percent), and `total_strings`.
    """
    tm = TranslationMemory(game_id=GAME_ID)
    stats = tm.get_stats()

    tracker = ProgressTracker(game_id=GAME_ID)
    mods = chrono_ark_adapter().scan_mods()

    total_strings = 0
    total_translated = 0

    for mod in mods:
        status = tracker.get_status(mod.mod_id)
        total_strings += status["total"]
        total_translated += status["translated"]

    return {
        "tm_entries": stats["total_entries"],
        "tm_hits": stats["session_hits"],
        "total_mods": len(mods),
        "global_progress": round((total_translated / total_strings * 100), 2) if total_strings > 0 else 0,
        "total_strings": total_strings,
    }
