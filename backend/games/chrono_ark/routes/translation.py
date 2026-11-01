"""Translation endpoints for the REST API."""

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.core.paths import glossary_path
from backend.core.settings import settings
from backend.data.glossary_manager import (
    load_glossary,
)
from backend.data.history_manager import create_backup
from backend.data.mod_settings import load_source_language_override, load_target_language_override
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.services.translation import batch_entries, load_mod_strings, persist_batch, prompt_context
from backend.routes.helpers import (
    _active_translations,
    chrono_ark_adapter,
    resolve_source_language,
)
from backend.routes.models import BatchTranslationRequest, TranslationRequest
from backend.routes.web_provider import ready_web_provider, web_provider
from backend.translation.orchestrator import chunk_entries
from backend.translation.pipeline import BatchJob, record_batch, run_translation_batch
from backend.translation.planning import plan_batches
from backend.translation.prompt import PromptContext

router = APIRouter(prefix="/translate")


@router.post("/estimate-all")
async def estimate_all_translation_costs(request: Request):
    """Estimate translation cost for all mods as if every string were untranslated, streaming one SSE event per mod.

    The final event carries `done: true`. The generator checks `request.is_disconnected` between mods so navigating away aborts early.

    Args:
        request: Starlette request, for disconnect detection.

    Returns:
        `StreamingResponse` of `text/event-stream` events.
    """
    mods = chrono_ark_adapter().scan_mods()
    provider_name = settings.translation_provider
    provider = web_provider(provider_name)

    async def event_stream():
        total = len(mods)
        base_glossary = load_glossary(glossary_path(GAME_ID))

        for i, mod in enumerate(mods):
            if await request.is_disconnected():
                return

            strings, _ = chrono_ark_adapter().extract_strings(mod.path)

            # Ignores existing English. Falls back to English for gdata/DLL strings that only have an English key in their translations dict.
            mod_lang_override = load_source_language_override(mod.mod_id, game_id=GAME_ID)
            mod_target_lang = load_target_language_override(mod.mod_id, game_id=GAME_ID) or "English"
            by_lang: dict[str, list[tuple[str, str]]] = {}
            entry_count = 0
            for key, loc_str in strings.items():
                lang = resolve_source_language(loc_str, mod_lang_override)
                if lang is None:
                    english = loc_str.translations.get("English", "").strip()
                    if english:
                        lang = "English"
                if lang is not None:
                    entry_count += 1
                    if lang not in by_lang:
                        by_lang[lang] = []
                    by_lang[lang].append((key, loc_str.translations.get(lang, "")))

            estimates = {lang: provider.estimate_cost(entries, **prompt_context(mod.mod_id, lang, mod_target_lang, base_glossary=base_glossary).provider_kwargs()) for lang, entries in by_lang.items()}

            event = {
                "current": i + 1,
                "total": total,
                "mod_id": mod.mod_id,
                "mod_name": mod.name,
                "total_strings": entry_count,
                "provider": provider.name,
                "estimates": estimates,
            }
            yield f"data: {json.dumps(event)}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/preview")
def preview_translation(req: TranslationRequest):
    """Preview the prompts that would be sent for each source language's batches.

    When `req.retranslate` is True, all translatable strings are included even if they already have English.

    Args:
        req: Mod id, optional provider override, and retranslate flag.

    Returns:
        `total_strings`, `total_batches`, `batch_size`, `provider`, `previews` and `estimates` per source language, and a flat `batch_plan`.
    """
    strings, target_lang = load_mod_strings(req.mod_id)
    adapter = chrono_ark_adapter()
    if req.retranslate:
        target = {key: loc_str for key, loc_str in strings.items() if not loc_str.untranslatable_reason or key.startswith("DLL/") if adapter.detect_source_language(loc_str) is not None}
    else:
        target = adapter.get_untranslated(strings, target_lang)

    if not target:
        return {"total_strings": 0, "message": "All strings already translated" if not req.retranslate else "No translatable strings found", "previews": {}}

    provider = web_provider(req.provider or settings.translation_provider)

    lang_override = load_source_language_override(req.mod_id, game_id=GAME_ID)
    by_lang: dict[str, list] = {}
    for key, loc_str in target.items():
        lang = resolve_source_language(loc_str, lang_override)
        if lang:
            by_lang.setdefault(lang, []).append((key, loc_str.translations.get(lang, "")))

    base_glossary = load_glossary(glossary_path(GAME_ID))
    chunks_by_lang = {lang: chunk_entries(entries, settings.batch_size, settings.batch_max_chars) for lang, entries in by_lang.items()}
    plan = plan_batches(provider, chunks_by_lang, lambda lang: prompt_context(req.mod_id, lang, target_lang, base_glossary=base_glossary))
    return {"total_strings": len(target), "batch_size": settings.batch_size, "provider": provider.name, **plan}


@router.get("/system-prompt")
async def get_system_prompt(source_lang: str = "Korean", target_lang: str = "English"):
    """Return the system prompt the active provider would send (no mod or entries needed).

    Args:
        source_lang: Source language for the prompt template.
        target_lang: Target language for the prompt template.

    Returns:
        `provider`, `source_lang`, and `system_prompt`.
    """
    provider = web_provider(settings.translation_provider)
    adapter = chrono_ark_adapter()
    context = PromptContext.for_adapter(adapter, source_lang, target_lang, adapter.get_base_glossary_prompt(source_lang=source_lang, target_lang=target_lang))
    system_prompt, _ = provider.build_prompt([("Example/Key_Name", "예시 텍스트")], **context.provider_kwargs())

    return {
        "provider": provider.name,
        "source_lang": source_lang,
        "system_prompt": system_prompt,
    }


def _load_batch(req: BatchTranslationRequest) -> tuple[dict, list[tuple[str, str]], str]:
    """Load the mod's strings and pick the batch's entries.

    Args:
        req: Batch request.

    Returns:
        (the mod's strings, the batch's (key, source_text) tuples, the target language).
    """
    strings, target_lang = load_mod_strings(req.mod_id)
    entries = batch_entries(strings, req.keys, req.source_lang)
    if not entries:
        raise HTTPException(status_code=400, detail="No translatable text found for the provided keys")
    return strings, entries, target_lang


async def _batch_job(req: BatchTranslationRequest) -> BatchJob:
    """Build a batch job, starting its provider and backing the mod up before a run's first batch.

    The glossary is reloaded on each call so newly accepted terms apply.

    Args:
        req: Batch request.

    Returns:
        The job.
    """
    strings, entries, target_lang = await asyncio.to_thread(_load_batch, req)
    provider_name = req.provider or settings.translation_provider
    provider = await ready_web_provider(provider_name)
    if req.is_first_batch:
        await asyncio.to_thread(create_backup, req.mod_id, "Before translation run", game_id=GAME_ID)
    context = await asyncio.to_thread(prompt_context, req.mod_id, req.source_lang, target_lang)
    persist = persist_batch(req.mod_id, provider_name, strings, entries, req.source_lang)
    return BatchJob(mod_id=req.mod_id, game_id=GAME_ID, provider=provider, provider_name=provider_name, entries=entries, context=context, persist=persist)


@router.post("/batch")
async def translate_batch(req: BatchTranslationRequest):
    """Translate one batch of explicit keys, for a frontend-driven loop that reviews glossary suggestions between batches.

    Args:
        req: Mod id, keys, source language, and first-batch flag.

    Returns:
        `translations` as `{key: text}`, `suggestions` for review, and the `translated` count.
    """
    job = await _batch_job(req)
    outcome = await asyncio.to_thread(run_translation_batch, job)
    return outcome.response()


@router.post("/cancel")
async def translate_cancel(mod_id: str = ""):
    """Signal an in-progress streaming translation to stop.

    Args:
        mod_id: Mod whose cancel event in `_active_translations` to set.
    """
    event = _active_translations.pop(mod_id, None)
    if event:
        event.set()
    return {"cancelled": event is not None}


@router.post("/batch/stream")
async def translate_batch_stream(req: BatchTranslationRequest, request: Request):
    """Translate one batch like `/translate/batch`, streaming SSE progress for providers that support it (currently Ollama).

    Non-streaming providers fall back to a single `complete` event.

    Args:
        req: Batch parameters (mod_id, provider, keys, etc.).
        request: Starlette request, to detect disconnect and stop Ollama early.
    """
    job = await _batch_job(req)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        loop = asyncio.get_event_loop()
        cancel_event = threading.Event()
        _active_translations[req.mod_id] = cancel_event

        def run_generator():
            try:
                for event in job.provider.translate_batch_stream(job.entries, cancel_event=cancel_event, **job.context.provider_kwargs()):
                    if cancel_event.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                if not cancel_event.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
            finally:
                _active_translations.pop(req.mod_id, None)
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, run_generator)

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except TimeoutError:
                if await request.is_disconnected():
                    cancel_event.set()
                    break
                continue

            if event is None:
                break

            if event.get("type") == "complete":
                # The review modal gets the same saved suggestions as a non-streamed batch, not the provider's raw list.
                outcome = await asyncio.to_thread(record_batch, job, event.get("translations", {}), event.get("suggestions", []))
                event["translations"] = outcome.translations
                event["suggestions"] = outcome.suggestions

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
