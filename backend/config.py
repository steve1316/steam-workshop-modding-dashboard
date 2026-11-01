"""
Central configuration, overridable via SWMT_-prefixed environment variables (legacy prefix from the old Mod Translator name).

Game-specific settings live in the game adapter under games/<game_id>/adapter.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# The Settings page writes this file, so values are read literally instead of expanding ${VAR}.
load_dotenv(Path(__file__).parent / ".env", interpolate=False)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Server
# Also consumed by the Vite frontend via define.
API_PORT = int(os.environ.get("SWMT_API_PORT", "8008"))

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Paths
STORAGE_PATH = Path(os.environ.get("SWMT_STORAGE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")))

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# API Keys
ANTHROPIC_API_KEY = os.environ.get("SWMT_ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("SWMT_OPENAI_API_KEY", "")
DEEPL_API_KEY = os.environ.get("SWMT_DEEPL_API_KEY", "")

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Model Selection
CLAUDE_MODEL = os.environ.get("SWMT_CLAUDE_MODEL", "claude-sonnet-5")
OPENAI_MODEL = os.environ.get("SWMT_OPENAI_MODEL", "gpt-4.1")

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Ollama Settings
OLLAMA_BASE_URL = os.environ.get("SWMT_OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("SWMT_OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_VRAM_TIER = os.environ.get("SWMT_OLLAMA_VRAM_TIER", "")

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# llama.cpp Settings
LLAMACPP_BASE_URL = os.environ.get("SWMT_LLAMACPP_BASE_URL", "http://localhost:8080")
LLAMACPP_MODEL = os.environ.get("SWMT_LLAMACPP_MODEL", "")
LLAMACPP_BINARY_PATH = os.environ.get("SWMT_LLAMACPP_BINARY_PATH", "llama-server")
LLAMACPP_MODEL_PATH = os.environ.get("SWMT_LLAMACPP_MODEL_PATH", "")
LLAMACPP_GPU_LAYERS = int(os.environ.get("SWMT_LLAMACPP_GPU_LAYERS", "-1"))
LLAMACPP_CTX_SIZE = int(os.environ.get("SWMT_LLAMACPP_CTX_SIZE", "8192"))
LLAMACPP_VRAM_TIER = os.environ.get("SWMT_LLAMACPP_VRAM_TIER", "")

# Directory for downloaded GGUF model files.
LLAMACPP_MODELS_DIR = Path(
    os.environ.get(
        "SWMT_LLAMACPP_MODELS_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "models"),
    )
)

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Translation Settings
# One of claude, openai, deepl, ollama, llamacpp, manual.
TRANSLATION_PROVIDER = os.environ.get("SWMT_TRANSLATION_PROVIDER", "claude")

# Strings per LLM API batch request.
BATCH_SIZE = int(os.environ.get("SWMT_BATCH_SIZE", "100"))

# Most source characters per batch, so batches of long strings get fewer keys and the reply fits the output token cap.
BATCH_MAX_CHARS = int(os.environ.get("SWMT_BATCH_MAX_CHARS", "6000"))

# Only these base glossary categories are sent to the LLM.
GLOSSARY_CATEGORIES = os.environ.get("SWMT_GLOSSARY_CATEGORIES", "characters,mechanics").split(",")

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Mod Filtering
# Comma-separated workshop mod IDs to hide.
IGNORED_MODS: list[str] = [m.strip() for m in os.environ.get("SWMT_IGNORED_MODS", "").split(",") if m.strip()]

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Game Selection
ACTIVE_GAME = os.environ.get("SWMT_ACTIVE_GAME", "chrono_ark")

TW3_HELPER_PATH = os.environ.get("SWMT_TW3_HELPER_PATH", "")
"""Filesystem path to the totalwar-modding helper_scripts/ directory.

Used by the script runner to subprocess Total War: Warhammer III pipelines.
Empty string = not yet configured.
"""

TW3_RPFM_CLI_PATH = os.environ.get("SWMT_TW3_RPFM_CLI_PATH", "")
"""Filesystem path to rpfm_cli.exe.

Defaults to `<TW3_HELPER_PATH>/rpfm_cli.exe` if blank, resolved at runtime by
the script runner preflight.
"""

TW3_STEAM_LIBRARY_DRIVE = os.environ.get("SWMT_TW3_STEAM_LIBRARY_DRIVE", "")
"""Drive letter where the user's Steam library lives, e.g. 'F:'.

Empty default means preflight will fail until the user configures it via
the env var or settings UI. Exposed to helper_scripts subprocess as the
STEAM_LIBRARY_DRIVE environment variable.
"""

STEAMCMD_PATH = os.environ.get("SWMT_STEAMCMD_PATH", "")
"""Absolute path to steamcmd.exe. Empty default disables the Publish to Workshop feature."""

STEAM_USERNAME = os.environ.get("SWMT_STEAM_USERNAME", "")
"""Steam account username used for `steamcmd +login`. No password is stored - SteamCMD relies on its cached sentry file from the user's one-time interactive login."""
