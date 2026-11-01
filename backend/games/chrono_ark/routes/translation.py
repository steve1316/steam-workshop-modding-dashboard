"""Translation endpoints for the REST API."""

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.core.paths import glossary_path
from backend.core.settings import settings
from backend.data import api_response_log
from backend.data.glossary_manager import (
    extract_name_key_suggestions,
    load_glossary,
    load_mod_glossary,
)
from backend.data.history_manager import create_backup
from backend.data.mod_settings import load_source_language_override, load_target_language_override
from backend.data.progress_tracker import ProgressTracker
from backend.data.suggestion_manager import add_suggestions, load_suggestions
from backend.data.translation_memory import TranslationMemory
from backend.data.translation_store import load_translations, save_translations_bulk
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.services.translation import prompt_context
from backend.routes.helpers import (
    _active_translations,
    _fill_duplicate_translations,
    _filter_suggestions,
    _find_mod_path,
    _merge_gdata_originals,
    chrono_ark_adapter,
    resolve_source_language,
)
from backend.routes.models import BatchTranslationRequest, TranslationRequest
from backend.routes.web_provider import ready_web_provider, web_provider
from backend.translation.orchestrator import chunk_entries, run_batch
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
async def preview_translation(req: TranslationRequest):
    """Preview the prompts that would be sent for each source language's batches.

    When `req.retranslate` is True, all translatable strings are included even if they already have English.

    Args:
        req: Mod id, optional provider override, and retranslate flag.

    Returns:
        `total_strings`, `total_batches`, `batch_size`, `provider`, `previews` and `estimates` per source language, and a flat `batch_plan`.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(req.mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(req.mod_id, strings, target_lang=target_lang)

    # Apply saved translations so user edits (including clears) are respected.
    saved = load_translations(req.mod_id, game_id=GAME_ID)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations[target_lang] = english

    if req.retranslate:
        target = {key: loc_str for key, loc_str in strings.items() if not loc_str.untranslatable_reason or key.startswith("DLL/") if chrono_ark_adapter().detect_source_language(loc_str) is not None}
    else:
        target = chrono_ark_adapter().get_untranslated(strings, target_lang)

    if not target:
        return {"total_strings": 0, "message": "All strings already translated" if not req.retranslate else "No translatable strings found", "previews": {}}

    provider = web_provider(req.provider or settings.translation_provider)

    lang_override = load_source_language_override(req.mod_id, game_id=GAME_ID)
    by_lang: dict[str, list] = {}
    for key, loc_str in target.items():
        lang = resolve_source_language(loc_str, lang_override)
        if lang:
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append((key, loc_str.translations.get(lang, "")))

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


@router.post("/batch")
async def translate_batch(req: BatchTranslationRequest):
    """Translate one batch of explicit keys, for a frontend-driven loop that reviews glossary suggestions between batches.

    The glossary is reloaded on each call so newly accepted terms apply.

    Args:
        req: Mod id, keys, source language, and first-batch flag.

    Returns:
        `translations` as `{key: English}`, `suggestions` for review, and the `translated` count.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(req.mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(req.mod_id, strings, target_lang=target_lang)

    # Saved translations win so user edits (including clears) are respected.
    saved = load_translations(req.mod_id, game_id=GAME_ID)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations[target_lang] = english

    entries: list[tuple[str, str]] = []
    for key in req.keys:
        if key in strings:
            source_text = strings[key].translations.get(req.source_lang, "")
            if source_text:
                entries.append((key, source_text))

    if not entries:
        raise HTTPException(status_code=400, detail="No translatable text found for the provided keys")

    provider_name = req.provider or settings.translation_provider
    provider = await ready_web_provider(provider_name)

    if req.is_first_batch:
        create_backup(req.mod_id, "Before translation run", game_id=GAME_ID)

    mod_glossary = load_mod_glossary(req.mod_id, game_id=GAME_ID)
    context = prompt_context(req.mod_id, req.source_lang, target_lang)

    tm = TranslationMemory(game_id=GAME_ID)

    try:
        translations, suggestions = await run_batch(provider, entries, context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    for key, english in translations.items():
        source_text = next((t for k, t in entries if k == key), "")
        if source_text and english:
            tm.store(source_text, english, req.source_lang)

    raw_responses = getattr(provider, "last_raw_responses", [])
    if raw_responses:
        api_response_log.log_batch_call(req.mod_id, game_id=GAME_ID, provider=provider_name, keys=[k for k, _ in entries], raw_responses=raw_responses)

    save_translations_bulk(req.mod_id, translations, game_id=GAME_ID, provider=provider_name)

    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.mark_translated(req.mod_id, list(translations.keys()))

    tm.save()

    filtered_suggestions = _filter_suggestions(suggestions, strings)

    # Name-key terms the provider didn't already suggest.
    existing_suggestions = load_suggestions(req.mod_id, game_id=GAME_ID)
    name_key_suggestions = extract_name_key_suggestions(
        translated_keys=list(translations.keys()),
        strings=strings,
        translations=translations,
        source_lang=req.source_lang,
        existing_suggestions=existing_suggestions + filtered_suggestions,
        mod_glossary=mod_glossary,
        term_categories=chrono_ark_adapter().get_glossary_categories(),
    )
    filtered_suggestions.extend(name_key_suggestions)

    if filtered_suggestions:
        add_suggestions(req.mod_id, filtered_suggestions, game_id=GAME_ID)

    return {
        "status": "success",
        "translated": len(translations),
        "translations": translations,
        "suggestions": filtered_suggestions,
    }


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
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(req.mod_id, game_id=GAME_ID) or "English"
    _merge_gdata_originals(req.mod_id, strings, target_lang=target_lang)

    saved = load_translations(req.mod_id, game_id=GAME_ID)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations[target_lang] = english

    entries: list[tuple[str, str]] = []
    for key in req.keys:
        if key in strings:
            source_text = strings[key].translations.get(req.source_lang, "")
            if source_text:
                entries.append((key, source_text))

    if not entries:
        raise HTTPException(status_code=400, detail="No translatable text found for the provided keys")

    provider_name = req.provider or settings.translation_provider
    provider = await ready_web_provider(provider_name)

    if req.is_first_batch:
        create_backup(req.mod_id, "Before translation run", game_id=GAME_ID)

    mod_glossary = load_mod_glossary(req.mod_id, game_id=GAME_ID)
    context = prompt_context(req.mod_id, req.source_lang, target_lang)

    tm = TranslationMemory(game_id=GAME_ID)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        loop = asyncio.get_event_loop()
        cancel_event = threading.Event()
        _active_translations[req.mod_id] = cancel_event

        def run_generator():
            try:
                for event in provider.translate_batch_stream(entries, cancel_event=cancel_event, **context.provider_kwargs()):
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
                translations = event.get("translations", {})
                suggestions = event.get("suggestions", [])

                # The LLM drops keys whose source text duplicates another entry's.
                _fill_duplicate_translations(translations, entries)
                event["translations"] = translations

                for key, english in translations.items():
                    source_text = next((t for k, t in entries if k == key), "")
                    if source_text and english:
                        tm.store(source_text, english, req.source_lang)

                raw_responses = getattr(provider, "last_raw_responses", [])
                if raw_responses:
                    api_response_log.log_batch_call(req.mod_id, game_id=GAME_ID, provider=provider_name, keys=[k for k, _ in entries], raw_responses=raw_responses)

                save_translations_bulk(req.mod_id, translations, game_id=GAME_ID, provider=provider_name)

                tracker = ProgressTracker(game_id=GAME_ID)
                tracker.mark_translated(req.mod_id, list(translations.keys()))

                tm.save()

                filtered_suggestions = _filter_suggestions(suggestions, strings)

                # Name-key terms the provider didn't already suggest.
                existing_suggestions = load_suggestions(req.mod_id, game_id=GAME_ID)
                name_key_suggestions = extract_name_key_suggestions(
                    translated_keys=list(translations.keys()),
                    strings=strings,
                    translations=translations,
                    source_lang=req.source_lang,
                    existing_suggestions=existing_suggestions + filtered_suggestions,
                    mod_glossary=mod_glossary,
                    term_categories=chrono_ark_adapter().get_glossary_categories(),
                )
                filtered_suggestions.extend(name_key_suggestions)

                if filtered_suggestions:
                    add_suggestions(req.mod_id, filtered_suggestions, game_id=GAME_ID)

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
