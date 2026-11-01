"""Build a translation provider from its id."""

from backend import config
from backend.providers.base import TranslationProvider
from backend.providers.claude_provider import ClaudeProvider
from backend.providers.deepl_provider import DeepLProvider
from backend.providers.llamacpp_provider import LlamaCppProvider
from backend.providers.manual_provider import ManualProvider
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openai_provider import OpenAIProvider


def get_provider(provider_name: str) -> TranslationProvider:
    """Create a translation provider instance by name.

    Args:
        provider_name: One of `"claude"`, `"openai"`, `"deepl"`, `"ollama"`, `"llamacpp"`, `"manual"`.

    Returns:
        Initialized provider.
    """
    if provider_name == "claude":
        return ClaudeProvider(model=config.CLAUDE_MODEL)
    elif provider_name == "openai":
        return OpenAIProvider(model=config.OPENAI_MODEL)
    elif provider_name == "deepl":
        return DeepLProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "llamacpp":
        return LlamaCppProvider()
    elif provider_name == "manual":
        return ManualProvider()
    raise ValueError(f"Unknown provider: {provider_name}. Available: claude, openai, deepl, ollama, llamacpp, manual")
