"""Pydantic request/response models for the REST API."""

from pydantic import BaseModel


class GlossaryTerm(BaseModel):
    """A global glossary term."""

    source: str
    english: str


class ModGlossaryTerm(BaseModel):
    """A mod-specific glossary term with per-language source mappings."""

    english: str
    source_mappings: dict[str, str] = {}
    category: str = "custom"


class SuggestionAction(BaseModel):
    """Payload for accepting or dismissing glossary suggestions.

    Attributes:
        terms: English terms to act on.
        all: Act on every pending suggestion regardless of `terms`.
        renames: Accept only. Maps a suggestion's English to the edited English, also renamed in translations whose source contains the term.
    """

    terms: list[str] = []
    all: bool = False
    renames: dict[str, str] = {}


class TranslationRequest(BaseModel):
    """Request body for translation, estimation, and preview endpoints.

    Attributes:
        provider: Overrides `settings.translation_provider` when set.
        scope: `"all"` (default), `"names"` (WH3 name strings only), or `"changed"` (WH3 Update Changed rows only).
    """

    mod_id: str
    provider: str | None = None
    retranslate: bool = False
    scope: str = "all"


class BatchTranslationRequest(BaseModel):
    """Request body for translating a single batch of strings.

    Attributes:
        is_first_batch: Creates a backup before translating.
        mode: `"translate"` (default) or `"update"` (WH3 revision of changed rows).
    """

    mod_id: str
    provider: str | None = None
    keys: list[str]
    source_lang: str
    is_first_batch: bool = False
    mode: str = "translate"


class TranslationUpdate(BaseModel):
    """Payload for manually updating one translated string.

    Attributes:
        english: New text. An empty string clears the translation.
    """

    key: str
    english: str


class CharacterContext(BaseModel):
    """Optional character lore context used to improve translation quality."""

    source_game: str = ""
    character_name: str = ""
    background: str = ""


class SourceLanguageOverride(BaseModel):
    """Payload for setting a per-mod source language override.

    Attributes:
        source_language: Language name, or None to revert to auto-detection.
    """

    source_language: str | None = None


class TargetLanguageOverride(BaseModel):
    """Payload for setting a per-mod target language override.

    Attributes:
        target_language: Language name, or None to revert to English.
    """

    target_language: str | None = None


class HistorySnapshotRequest(BaseModel):
    """Payload for creating a manual history snapshot.

    Attributes:
        label: Snapshot description, defaulted when blank.
    """

    label: str = ""


class SettingsResponse(BaseModel):
    """Current application settings returned by GET /api/settings.

    Attributes:
        anthropic_api_key_set: Masked key (e.g. `"****ab12"`) or empty string if unset. Same for the OpenAI and DeepL keys.
        ollama_status: `"running"`, `"stopped"`, or `"not_installed"`.
        llamacpp_gpu_layers: Layers to offload to GPU (-1 = all).
        ollama_managed: Whether this app spawned the running Ollama process.
        llamacpp_managed: Whether this app spawned the running llama-server process.
        tw3_rpfm_cli_path: Blank means the default inside helper_scripts.
        steam_username: For `steamcmd +login`. No password is stored.
    """

    provider: str
    batch_size: int
    anthropic_api_key_set: str
    openai_api_key_set: str
    deepl_api_key_set: str
    claude_model: str
    openai_model: str
    ollama_base_url: str
    ollama_model: str
    ollama_vram_tier: str
    ollama_status: str
    llamacpp_base_url: str
    llamacpp_model: str
    llamacpp_binary_path: str
    llamacpp_model_path: str
    llamacpp_gpu_layers: int
    llamacpp_ctx_size: int
    llamacpp_vram_tier: str
    ollama_managed: bool
    llamacpp_managed: bool
    ignored_mods: list[str]
    active_game: str
    tw3_helper_path: str = ""
    tw3_rpfm_cli_path: str = ""
    tw3_steam_library_drive: str = ""
    steamcmd_path: str = ""
    steam_username: str = ""
    games: dict[str, dict] = {}


class SettingsUpdate(BaseModel):
    """Payload for POST /api/settings.

    Every field is optional and `None` fields are left unchanged.
    """

    provider: str | None = None
    batch_size: int | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepl_api_key: str | None = None
    claude_model: str | None = None
    openai_model: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    ollama_vram_tier: str | None = None
    llamacpp_base_url: str | None = None
    llamacpp_model: str | None = None
    llamacpp_binary_path: str | None = None
    llamacpp_model_path: str | None = None
    llamacpp_gpu_layers: int | None = None
    llamacpp_ctx_size: int | None = None
    llamacpp_vram_tier: str | None = None
    ignored_mods: list[str] | None = None
    active_game: str | None = None
    tw3_helper_path: str | None = None
    tw3_rpfm_cli_path: str | None = None
    tw3_steam_library_drive: str | None = None
    steamcmd_path: str | None = None
    steam_username: str | None = None


class OllamaPullRequest(BaseModel):
    """Request body for POST /api/ollama/pull."""

    model: str


class LlamaCppInstallRequest(BaseModel):
    """Request body for POST /api/llamacpp/install.

    Attributes:
        backend: GPU backend to download (e.g. `"vulkan"`, `"cuda-12"`).
    """

    backend: str = "vulkan"


class GGUFDownloadRequest(BaseModel):
    """Request body for POST /api/llamacpp/download."""

    url: str
    filename: str
