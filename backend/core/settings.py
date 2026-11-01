"""App settings read from `SWMT_`-prefixed env vars and the backend `.env` file (prefix kept from the old Mod Translator name).

Routes assign fields at runtime when the Settings page saves, so every reader sees the new value without a restart.
"""

from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from backend.core.env_file import ENV_PATH

_BACKEND_DIR = Path(__file__).resolve().parent.parent

# The Settings page writes this file, so values are read literally instead of expanding ${VAR}.
load_dotenv(ENV_PATH, interpolate=False)

CommaList = Annotated[list[str], NoDecode]
"""A list stored in the env as comma-separated text instead of JSON."""


class TotalWarWarhammer3Settings(BaseSettings):
    """Total War: Warhammer III paths, read from `SWMT_TW3_*`."""

    model_config = SettingsConfigDict(env_prefix="SWMT_TW3_", extra="ignore")

    # Empty means not yet configured.
    helper_path: str = ""
    """Path to the totalwar-modding helper_scripts/ directory the script runner shells into."""

    rpfm_cli_path: str = ""
    """Path to rpfm_cli.exe. Blank falls back to `<helper_path>/rpfm_cli.exe` at runtime."""

    steam_library_drive: str = ""
    """Drive letter of the Steam library, e.g. `F:`. Passed to helper_scripts as `STEAM_LIBRARY_DRIVE`."""


class Settings(BaseSettings):
    """Every app setting, one field per `SWMT_<FIELD>` env var."""

    model_config = SettingsConfigDict(env_prefix="SWMT_", extra="ignore")

    # Also read by the Vite frontend.
    api_port: int = 8008
    storage_path: Path = _BACKEND_DIR / "storage"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepl_api_key: str = ""

    claude_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-4.1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_vram_tier: str = ""

    llamacpp_base_url: str = "http://localhost:8080"
    llamacpp_model: str = ""
    llamacpp_binary_path: str = "llama-server"
    llamacpp_model_path: str = ""
    llamacpp_gpu_layers: int = -1
    llamacpp_ctx_size: int = 8192
    llamacpp_vram_tier: str = ""
    llamacpp_models_dir: Path = _BACKEND_DIR / "storage" / "models"
    """Directory for downloaded GGUF model files."""

    translation_provider: str = "claude"
    """One of claude, openai, deepl, ollama, llamacpp, manual."""

    batch_size: int = 100
    """Strings per LLM API batch request."""

    batch_max_chars: int = 6000
    """Most source characters per batch, so batches of long strings get fewer keys and the reply fits the output token cap."""

    glossary_categories: CommaList = ["characters", "mechanics"]
    """Base glossary categories sent to the LLM."""

    ignored_mods: CommaList = []
    """Workshop mod ids hidden from the mod list."""

    active_game: str = "chrono_ark"

    base_game_path: Path = Path(r"F:\SteamLibrary\steamapps\common\Chrono Ark\ChronoArk_Data\StreamingAssets")
    """Chrono Ark `StreamingAssets` folder holding the base-game localization CSVs."""

    workshop_path: Path = Path(r"F:\SteamLibrary\steamapps\workshop\content\1188930")
    """Chrono Ark Steam Workshop content folder."""

    steamcmd_path: str = ""
    """Path to steamcmd.exe. Empty disables Publish to Workshop."""

    steam_username: str = ""
    """Account for `steamcmd +login`. No password is stored because SteamCMD reuses the sentry file from a one-time interactive login."""

    tw3: TotalWarWarhammer3Settings = Field(default_factory=TotalWarWarhammer3Settings)

    @field_validator("glossary_categories", "ignored_mods", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        """Split a comma-separated env string into trimmed, non-empty items.

        Args:
            value: Raw field input.

        Returns:
            List of items, or the input unchanged when it is not a string.
        """
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
"""Process-wide settings. Assign fields on this object to change a setting at runtime."""
