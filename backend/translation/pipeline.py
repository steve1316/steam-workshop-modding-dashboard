"""One translate-batch flow for every game: provider call, duplicate fill and API log, then the game's own persistence hook.

Both entry points block on the provider and on disk, so async routes run them through `asyncio.to_thread`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.core.errors import UpstreamError
from backend.data import api_response_log
from backend.providers.base import TranslationProvider
from backend.translation.orchestrator import fill_duplicate_translations
from backend.translation.prompt import PromptContext


@dataclass(frozen=True)
class BatchOutcome:
    """What a finished batch saved.

    Attributes:
        translations: Key -> translated text as persisted.
        suggestions: Glossary suggestions left for the user to review.
    """

    translations: dict[str, str]
    suggestions: list[dict]

    def response(self) -> dict:
        """Return the `/translate/batch` response body.

        Returns:
            Dict with `status`, `translated`, `translations` and `suggestions`.
        """
        return {"status": "success", "translated": len(self.translations), "translations": self.translations, "suggestions": self.suggestions}


# Saves a batch's translations and suggestions the game's way and returns what was kept.
PersistHook = Callable[[dict[str, str], list[dict]], BatchOutcome]


class BatchError(UpstreamError):
    """The provider call for a batch failed. The message is the provider's error."""


@dataclass(frozen=True)
class BatchJob:
    """One batch to translate and where its results go.

    Attributes:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.
        provider: Provider that runs the batch.
        provider_name: Provider id recorded on saved rows and in the API log.
        entries: (key, source_text) tuples.
        context: Languages, glossary and game rules for the prompt.
        persist: The game's persistence hook.
    """

    mod_id: str
    game_id: str
    provider: TranslationProvider
    provider_name: str
    entries: list[tuple[str, str]]
    context: PromptContext
    persist: PersistHook


def record_batch(job: BatchJob, translations: dict[str, str], suggestions: list[dict]) -> BatchOutcome:
    """Finish a batch the provider already ran: fill deduplicated keys, log the call, then persist.

    Args:
        job: The batch.
        translations: Provider's key -> translated text.
        suggestions: Provider's suggested glossary terms.

    Returns:
        What the persistence hook kept.
    """
    fill_duplicate_translations(translations, job.entries)
    _log(job)
    return job.persist(translations, suggestions)


def run_translation_batch(job: BatchJob) -> BatchOutcome:
    """Translate one batch and persist it.

    Args:
        job: The batch.

    Returns:
        What the persistence hook kept.
    """
    job.provider.last_raw_responses = []
    try:
        translations, suggestions = job.provider.translate_batch(job.entries, **job.context.provider_kwargs())
    except Exception as e:
        _log(job, error=str(e))
        raise BatchError(str(e)) from e
    return record_batch(job, translations, suggestions)


def _log(job: BatchJob, error: str | None = None) -> None:
    """Record the batch's provider call in the API-response log.

    Args:
        job: The batch.
        error: Error message when the call failed.
    """
    raw_responses = getattr(job.provider, "last_raw_responses", [])
    # Providers with no raw text to show, such as DeepL, leave nothing worth logging on success.
    if raw_responses or error:
        api_response_log.log_batch_call(job.mod_id, game_id=job.game_id, provider=job.provider_name, keys=[k for k, _ in job.entries], raw_responses=raw_responses, error=error)
