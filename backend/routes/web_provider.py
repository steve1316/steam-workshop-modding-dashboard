"""Build translation providers for web requests, which every game's translate routes share."""

from fastapi import HTTPException

from backend.providers.base import TranslationProvider
from backend.providers.factory import get_provider
from backend.routes.llamacpp import _ensure_llamacpp_running


def web_provider(provider_name: str) -> TranslationProvider:
    """Build a provider for a web request, turning unusable names into a 400.

    Args:
        provider_name: Provider id from the request or config.

    Returns:
        Initialized `TranslationProvider`.
    """
    # Manual mode blocks on `input()`, which would hang the server.
    if provider_name == "manual":
        raise HTTPException(status_code=400, detail="Manual mode only works from the CLI. Pick another provider in Settings.")
    try:
        return get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


async def ready_web_provider(provider_name: str) -> TranslationProvider:
    """Build a provider for a request that will call it, starting llama-server first when it is the one picked.

    Args:
        provider_name: Provider id from the request or config.

    Returns:
        Initialized `TranslationProvider`.
    """
    if provider_name == "llamacpp":
        await _ensure_llamacpp_running()
    return web_provider(provider_name)
