"""Translation endpoints for the REST API."""

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend import config
from backend.translation.game_storage import GameStorage
from backend.translation.orchestrator import chunk_entries, run_batch
from backend.data.character_context import load_character_context
from backend.data.glossary_manager import (
    get_combined_glossary_prompt,
    extract_name_key_suggestions,
    load_glossary,
    load_mod_glossary,
)
from backend.data.history_manager import create_backup
from backend.data.progress_tracker import ProgressTracker
from backend.data.suggestion_manager import add_suggestions, load_suggestions
from backend.data.translation_memory import TranslationMemory
from backend.data.translation_store import load_translations, save_translations_bulk
from backend.main import get_provider
from backend.data.mod_settings import load_source_language_override, load_target_language_override
from backend.routes.helpers import (
    chrono_ark_adapter,
    _active_translations,
    _fill_duplicate_translations,
    _filter_suggestions,
    _find_mod_path,
    _merge_gdata_originals,
    _stamp_raw_responses,
    resolve_source_language,
)
from backend.routes.llamacpp import _ensure_llamacpp_running
from backend.routes.models import BatchTranslationRequest, TranslationRequest

router = APIRouter(prefix="/translate")


def _web_provider(provider_name: str):
    """Build a provider for a web request, turning unusable names into a 400.

    Args:
        provider_name: The provider id from the request or config.

    Returns:
        The initialized TranslationProvider.
    """
    # Manual mode blocks on `input()`, which would hang the server.
    if provider_name == "manual":
        raise HTTPException(status_code=400, detail="Manual mode only works from the CLI. Pick another provider in Settings.")
    try:
        return get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/estimate")
async def estimate_translation(req: TranslationRequest):
    """Estimate cost and time for translating a mod.

    Args:
        req: Translation request containing the mod id and optional provider
            override.

    Returns:
        A dict with `total_strings`, `provider` name, and `estimates`
        keyed by source language, each containing the provider's cost and
        token estimates.

    Raises:
        HTTPException: 404 if no mod with the given id is found.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    untranslated = chrono_ark_adapter().get_untranslated(strings)

    if not untranslated:
        return {"total": 0, "estimates": {}}

    provider_name = req.provider or config.TRANSLATION_PROVIDER
    provider = _web_provider(provider_name)

    # Group by language
    lang_override = load_source_language_override(req.mod_id)
    target_lang = load_target_language_override(req.mod_id) or "English"
    by_lang = {}
    for key, loc_str in untranslated.items():
        lang = resolve_source_language(loc_str, lang_override)
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append((key, loc_str.translations.get(lang, "")))

    # Load glossary and context for accurate cost estimation.
    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(req.mod_id)
    game_context = chrono_ark_adapter().get_translation_context()
    char_ctx = load_character_context(req.mod_id)
    character_context = char_ctx if any(char_ctx.values()) else None
    format_rules = chrono_ark_adapter().get_format_preservation_rules()

    estimates = {}
    for lang, entries in by_lang.items():
        glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang, target_lang=target_lang)
        estimates[lang] = provider.estimate_cost(
            entries,
            source_lang=lang,
            glossary_prompt=glossary_prompt,
            game_context=game_context,
            format_rules=format_rules,
            style_examples=chrono_ark_adapter().get_style_examples(lang),
            character_context=character_context,
            target_lang=target_lang,
        )

    return {"total_strings": len(untranslated), "provider": provider.name, "estimates": estimates}


@router.post("/estimate-all")
async def estimate_all_translation_costs(request: Request):
    """Estimate translation cost for all mods, treating every string as untranslated.

    Streams SSE progress events as each mod is processed. Each event
    contains the mod's id, name, string count, and per-language cost
    estimates. The final event carries `done: true`.

    The generator checks `request.is_disconnected` between mods so that
    navigating away or refreshing the page aborts the work early.

    Args:
        request: The Starlette request, used for disconnect detection.

    Returns:
        A `StreamingResponse` of `text/event-stream` SSE events.
    """
    mods = chrono_ark_adapter().scan_mods()
    provider_name = config.TRANSLATION_PROVIDER
    provider = _web_provider(provider_name)

    async def event_stream():
        total = len(mods)
        base_glossary = load_glossary()
        game_context = chrono_ark_adapter().get_translation_context()
        format_rules = chrono_ark_adapter().get_format_preservation_rules()

        for i, mod in enumerate(mods):
            if await request.is_disconnected():
                return

            strings, _ = chrono_ark_adapter().extract_strings(mod.path)

            # Treat ALL strings as needing translation (ignore existing English).
            # Detect source language once per string to avoid redundant calls.
            # Fall back to Chinese for gdata/DLL strings that only have an
            # English key in their translations dict.
            mod_lang_override = load_source_language_override(mod.mod_id)
            mod_target_lang = load_target_language_override(mod.mod_id) or "English"
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

            estimates = {}
            if by_lang:
                mod_glossary = load_mod_glossary(mod.mod_id)
                char_ctx = load_character_context(mod.mod_id)
                character_context = char_ctx if any(char_ctx.values()) else None

                for lang, entries in by_lang.items():
                    glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang, target_lang=mod_target_lang)
                    estimates[lang] = provider.estimate_cost(
                        entries,
                        source_lang=lang,
                        glossary_prompt=glossary_prompt,
                        game_context=game_context,
                        format_rules=format_rules,
                        style_examples=chrono_ark_adapter().get_style_examples(lang),
                        character_context=character_context,
                        target_lang=mod_target_lang,
                    )

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
    """Preview the translation prompt that will be sent to the provider.

    Builds the system prompt and user message for the first batch of each
    source language so the user can inspect what will be sent before
    committing to a full translation run.

    When `req.retranslate` is True, all translatable strings are included
    regardless of whether they already have an English translation.

    Args:
        req: Translation request containing the mod id, optional provider
            override, and optional retranslate flag.

    Returns:
        A dict with `total_strings`, `total_batches`, `batch_size`,
        `provider` name, `previews` keyed by source language (each
        containing the prompts and batch metadata), and `estimates` with
        per-language cost estimates.

    Raises:
        HTTPException: 404 if no mod with the given id is found.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(req.mod_id, strings)

    # Apply saved translations so user edits (including clears) are respected.
    saved = load_translations(req.mod_id)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations["English"] = english

    if req.retranslate:
        # Re-translate: include all strings that have source text, even if
        # they already have an English translation.
        target = {key: loc_str for key, loc_str in strings.items() if not loc_str.untranslatable_reason or key.startswith("DLL/") if chrono_ark_adapter().detect_source_language(loc_str) is not None}
    else:
        target = chrono_ark_adapter().get_untranslated(strings)

    if not target:
        return {"total_strings": 0, "message": "All strings already translated" if not req.retranslate else "No translatable strings found", "previews": {}}

    provider_name = req.provider or config.TRANSLATION_PROVIDER
    provider = _web_provider(provider_name)

    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(req.mod_id)
    game_context = chrono_ark_adapter().get_translation_context()
    char_ctx = load_character_context(req.mod_id)
    character_context = char_ctx if any(char_ctx.values()) else None
    format_rules = chrono_ark_adapter().get_format_preservation_rules()

    lang_override = load_source_language_override(req.mod_id)
    target_lang = load_target_language_override(req.mod_id) or "English"
    by_lang: dict[str, list] = {}
    for key, loc_str in target.items():
        lang = resolve_source_language(loc_str, lang_override)
        if lang:
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append((key, loc_str.translations.get(lang, "")))

    batch_size = config.BATCH_SIZE
    previews = {}
    estimates = {}
    total_batches = 0
    for lang, entries in by_lang.items():
        glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang, target_lang=target_lang)
        style_examples = chrono_ark_adapter().get_style_examples(lang)
        batches = chunk_entries(entries, batch_size, config.BATCH_MAX_CHARS)
        num_batches = len(batches)
        total_batches += num_batches
        user_messages: list[str] = []
        system_prompt = ""
        for batch in batches:
            sp, um = provider.build_prompt(
                batch,
                lang,
                glossary_prompt,
                game_context=game_context,
                format_rules=format_rules,
                style_examples=style_examples,
                character_context=character_context,
                target_lang=target_lang,
            )
            if not system_prompt:
                system_prompt = sp
            user_messages.append(um)
        previews[lang] = {
            "system_prompt": system_prompt,
            "user_messages": user_messages,
            "strings_in_language": len(entries),
            "batches": num_batches,
        }
        estimates[lang] = provider.estimate_cost(
            entries,
            source_lang=lang,
            glossary_prompt=glossary_prompt,
            game_context=game_context,
            format_rules=format_rules,
            style_examples=style_examples,
            character_context=character_context,
            target_lang=target_lang,
        )

    # Build a flat batch plan the frontend can iterate over.
    batch_plan = []
    for lang, entries in by_lang.items():
        for batch in chunk_entries(entries, batch_size, config.BATCH_MAX_CHARS):
            batch_plan.append(
                {
                    "source_lang": lang,
                    "keys": [key for key, _ in batch],
                    "size": len(batch),
                }
            )

    return {
        "total_strings": len(target),
        "total_batches": total_batches,
        "batch_size": batch_size,
        "provider": provider.name,
        "previews": previews,
        "estimates": estimates,
        "batch_plan": batch_plan,
    }


@router.get("/system-prompt")
async def get_system_prompt(source_lang: str = "Korean", target_lang: str = "English"):
    """Return the current system prompt that would be sent to the provider.

    Builds the prompt using the active provider, base glossary, game context,
    format rules, and style examples. No mod or entries are needed.

    Args:
        source_lang: Source language to use in the prompt template.

    Returns:
        A dict with `provider`, `source_lang`, and `system_prompt`.
    """
    provider_name = config.TRANSLATION_PROVIDER
    provider = _web_provider(provider_name)

    glossary_prompt = chrono_ark_adapter().get_base_glossary_prompt(source_lang=source_lang, target_lang=target_lang)
    game_context = chrono_ark_adapter().get_translation_context()
    format_rules = chrono_ark_adapter().get_format_preservation_rules()

    system_prompt, _ = provider.build_prompt(
        entries=[("Example/Key_Name", "예시 텍스트")],
        source_lang=source_lang,
        glossary_prompt=glossary_prompt,
        game_context=game_context,
        format_rules=format_rules,
        style_examples=chrono_ark_adapter().get_style_examples(source_lang),
        target_lang=target_lang,
    )

    return {
        "provider": provider.name,
        "source_lang": source_lang,
        "system_prompt": system_prompt,
    }


@router.post("")
async def translate_mod(req: TranslationRequest):
    """Trigger translation for a mod.

    Sends all untranslated strings to the configured AI provider in batches,
    saves the resulting translations, updates progress tracking, and stores
    any glossary suggestions returned by the provider.

    Args:
        req: Translation request containing the mod id and optional provider
            override.

    Returns:
        A dict with `status`, the count of `translated` strings, the
        count of `suggestions` received, and a `translations` mapping
        of key to English text.

    Raises:
        HTTPException: 404 if no mod with the given id is found.
        HTTPException: 502 if the translation provider returns an error.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    target_lang = load_target_language_override(req.mod_id) or "English"

    # Apply saved translations so user edits (including clears) are respected.
    saved = load_translations(req.mod_id)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations[target_lang] = english

    untranslated = chrono_ark_adapter().get_untranslated(strings)

    provider_name = req.provider or config.TRANSLATION_PROVIDER
    provider = _web_provider(provider_name)

    if not untranslated:
        return {"status": "complete", "message": "All strings already translated", "translated": 0, "suggestions": 0}

    # Load glossaries.
    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(req.mod_id)
    game_context = chrono_ark_adapter().get_translation_context()
    char_ctx = load_character_context(req.mod_id)
    character_context = char_ctx if any(char_ctx.values()) else None
    format_rules = chrono_ark_adapter().get_format_preservation_rules()

    # Translate.
    tm = TranslationMemory()
    all_translations: dict[str, str] = {}
    all_suggestions: list[dict] = []

    lang_override = load_source_language_override(req.mod_id)
    by_lang: dict[str, list] = {}
    for key, loc_str in untranslated.items():
        lang = resolve_source_language(loc_str, lang_override)
        if lang:
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append((key, loc_str.translations.get(lang, "")))

    # Back up before translation run.
    create_backup(req.mod_id, "Before translation run")

    # Reset raw response tracking on the provider
    if hasattr(provider, "last_raw_responses"):
        provider.last_raw_responses = []

    batch_size = config.BATCH_SIZE
    loop = asyncio.get_running_loop()
    try:
        for lang, entries in by_lang.items():
            glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang, target_lang=target_lang)
            style_examples = chrono_ark_adapter().get_style_examples(lang)
            for batch in chunk_entries(entries, batch_size, config.BATCH_MAX_CHARS):
                translations, suggestions = await loop.run_in_executor(
                    None,
                    lambda batch=batch, lang=lang, glossary_prompt=glossary_prompt: provider.translate_batch(
                        batch,
                        lang,
                        glossary_prompt,
                        game_context=game_context,
                        format_rules=format_rules,
                        style_examples=style_examples,
                        character_context=character_context,
                        target_lang=target_lang,
                    ),
                )
                _fill_duplicate_translations(translations, batch)
                all_translations.update(translations)
                all_suggestions.extend(suggestions)

                for key, english in translations.items():
                    source_text = next((t for k, t in batch if k == key), "")
                    if source_text and english:
                        tm.store(source_text, english, lang)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Save raw API responses for inspection
    raw_responses = getattr(provider, "last_raw_responses", [])
    if raw_responses:
        _stamp_raw_responses(raw_responses)
        responses_path = GameStorage("chrono_ark").mod_file(req.mod_id, "last_api_responses.json")
        responses_path.parent.mkdir(parents=True, exist_ok=True)
        with open(responses_path, "w", encoding="utf-8") as f:
            json.dump(raw_responses, f, indent=2, ensure_ascii=False)

    # Save translations.
    save_translations_bulk(req.mod_id, all_translations)

    # Update progress.
    tracker = ProgressTracker()
    tracker.mark_translated(req.mod_id, list(all_translations.keys()))

    # Save TM.
    tm.save()

    filtered_suggestions = _filter_suggestions(all_suggestions, strings)

    # Auto-detect name-key terms not already suggested by the provider.
    existing_suggestions = load_suggestions(req.mod_id)
    combined_existing = existing_suggestions + filtered_suggestions
    for lang, entries in by_lang.items():
        lang_keys = [k for k, _ in entries if k in all_translations]
        name_key_suggestions = extract_name_key_suggestions(
            translated_keys=lang_keys,
            strings=strings,
            translations=all_translations,
            source_lang=lang,
            existing_suggestions=combined_existing,
            mod_glossary=mod_glossary,
            term_categories=chrono_ark_adapter().get_glossary_categories(),
        )
        filtered_suggestions.extend(name_key_suggestions)
        combined_existing.extend(name_key_suggestions)

    # Store suggestions (add_suggestions deduplicates internally).
    if filtered_suggestions:
        add_suggestions(req.mod_id, filtered_suggestions)

    # Return the actual stored count (post-dedup) so the UI is accurate.
    stored_suggestions = load_suggestions(req.mod_id)

    return {
        "status": "success",
        "translated": len(all_translations),
        "suggestions": len(stored_suggestions),
        "translations": all_translations,
    }


@router.post("/batch")
async def translate_batch(req: BatchTranslationRequest):
    """Translate a single batch of strings by explicit keys.

    Designed for iterative batch translation where the frontend drives the
    loop, allowing the user to review glossary suggestions between batches.
    The glossary is reloaded fresh each call so newly accepted terms from
    previous batch reviews are included.

    Args:
        req: Batch translation request with mod_id, explicit keys,
            source_lang, and whether this is the first batch.

    Returns:
        A dict with `translations` (key->english), `suggestions` (full
        suggestion objects for review), and `translated` count.

    Raises:
        HTTPException: 404 if the mod is not found.
        HTTPException: 400 if none of the provided keys have translatable text.
        HTTPException: 502 if the translation provider returns an error.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(req.mod_id, strings)
    target_lang = load_target_language_override(req.mod_id) or "English"

    # Apply saved translations so user edits (including clears) are respected.
    saved = load_translations(req.mod_id)
    for key, english in saved.items():
        if key in strings:
            strings[key].translations[target_lang] = english

    # Build entries list from the explicit keys.
    entries: list[tuple[str, str]] = []
    for key in req.keys:
        if key in strings:
            source_text = strings[key].translations.get(req.source_lang, "")
            if source_text:
                entries.append((key, source_text))

    if not entries:
        raise HTTPException(status_code=400, detail="No translatable text found for the provided keys")

    provider_name = req.provider or config.TRANSLATION_PROVIDER

    if provider_name == "llamacpp":
        await _ensure_llamacpp_running()

    provider = _web_provider(provider_name)

    # Create backup and reset raw responses only on the first batch.
    if req.is_first_batch:
        create_backup(req.mod_id, "Before translation run")
        if hasattr(provider, "last_raw_responses"):
            provider.last_raw_responses = []

    # Re-load glossaries fresh (picks up terms accepted between batches).
    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(req.mod_id)
    glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=req.source_lang, target_lang=target_lang)

    game_context = chrono_ark_adapter().get_translation_context()
    char_ctx = load_character_context(req.mod_id)
    character_context = char_ctx if any(char_ctx.values()) else None
    format_rules = chrono_ark_adapter().get_format_preservation_rules()
    style_examples = chrono_ark_adapter().get_style_examples(req.source_lang)

    tm = TranslationMemory()

    try:
        translations, suggestions = await run_batch(
            provider,
            entries,
            req.source_lang,
            glossary_prompt,
            game_context=game_context,
            format_rules=format_rules,
            style_examples=style_examples,
            character_context=character_context,
            target_lang=target_lang,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Store translation memory entries.
    for key, english in translations.items():
        source_text = next((t for k, t in entries if k == key), "")
        if source_text and english:
            tm.store(source_text, english, req.source_lang)

    # Append raw API responses for inspection (accumulate across batches).
    raw_responses = getattr(provider, "last_raw_responses", [])
    if raw_responses:
        _stamp_raw_responses(raw_responses)
        responses_path = GameStorage("chrono_ark").mod_file(req.mod_id, "last_api_responses.json")
        responses_path.parent.mkdir(parents=True, exist_ok=True)
        existing_responses = []
        if not req.is_first_batch and responses_path.exists():
            try:
                with open(responses_path, "r", encoding="utf-8") as f:
                    existing_responses = json.load(f)
            except Exception:
                pass
        existing_responses.extend(raw_responses)
        with open(responses_path, "w", encoding="utf-8") as f:
            json.dump(existing_responses, f, indent=2, ensure_ascii=False)

    # Save translations incrementally.
    save_translations_bulk(req.mod_id, translations)

    # Track which provider translated each key.
    providers_path = GameStorage("chrono_ark").mod_file(req.mod_id, "translation_providers.json")
    existing_providers: dict[str, str] = {}
    if providers_path.exists():
        try:
            with open(providers_path, "r", encoding="utf-8") as f:
                existing_providers = json.load(f)
        except Exception:
            pass
    for key in translations:
        existing_providers[key] = provider_name
    with open(providers_path, "w", encoding="utf-8") as f:
        json.dump(existing_providers, f, indent=2, ensure_ascii=False)

    # Update progress.
    tracker = ProgressTracker()
    tracker.mark_translated(req.mod_id, list(translations.keys()))

    # Save TM.
    tm.save()

    # Filter and store suggestions.
    filtered_suggestions = _filter_suggestions(suggestions, strings)

    # Auto-detect name-key terms not already suggested by the provider.
    existing_suggestions = load_suggestions(req.mod_id)
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
        add_suggestions(req.mod_id, filtered_suggestions)

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
        mod_id: The mod whose translation should be cancelled.  Looks up the
            corresponding cancel event in `_active_translations`.
    """
    event = _active_translations.pop(mod_id, None)
    if event:
        event.set()
    return {"cancelled": event is not None}


@router.post("/batch/stream")
async def translate_batch_stream(req: BatchTranslationRequest, request: Request):
    """Translate a single batch with real-time SSE progress events.

    Same logic as `/api/games/chrono_ark/translate/batch` but streams progress events for
    providers that support it (currently Ollama).  Non-streaming providers
    fall back to a single `complete` event.

    Args:
        req: Batch translation parameters (mod_id, provider, keys, etc.).
        request: The underlying Starlette request, used to detect client
            disconnection so the Ollama process can be stopped early.
    """
    mod_path = _find_mod_path(req.mod_id)

    strings, _ = chrono_ark_adapter().extract_strings(mod_path)
    _merge_gdata_originals(req.mod_id, strings)
    target_lang = load_target_language_override(req.mod_id) or "English"

    saved = load_translations(req.mod_id)
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

    provider_name = req.provider or config.TRANSLATION_PROVIDER

    if provider_name == "llamacpp":
        await _ensure_llamacpp_running()

    provider = _web_provider(provider_name)

    if req.is_first_batch:
        create_backup(req.mod_id, "Before translation run")
        if hasattr(provider, "last_raw_responses"):
            provider.last_raw_responses = []

    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(req.mod_id)
    glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=req.source_lang, target_lang=target_lang)

    game_context = chrono_ark_adapter().get_translation_context()
    char_ctx = load_character_context(req.mod_id)
    character_context = char_ctx if any(char_ctx.values()) else None
    format_rules = chrono_ark_adapter().get_format_preservation_rules()
    style_examples = chrono_ark_adapter().get_style_examples(req.source_lang)

    tm = TranslationMemory()

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        loop = asyncio.get_event_loop()
        cancel_event = threading.Event()
        _active_translations[req.mod_id] = cancel_event

        def run_generator():
            try:
                for event in provider.translate_batch_stream(
                    entries,
                    req.source_lang,
                    glossary_prompt,
                    game_context=game_context,
                    format_rules=format_rules,
                    style_examples=style_examples,
                    character_context=character_context,
                    cancel_event=cancel_event,
                    target_lang=target_lang,
                ):
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
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    cancel_event.set()
                    break
                continue

            if event is None:
                break

            if event.get("type") == "complete":
                translations = event.get("translations", {})
                suggestions = event.get("suggestions", [])

                # Fill in keys the LLM dropped due to duplicate source text.
                _fill_duplicate_translations(translations, entries)
                event["translations"] = translations

                for key, english in translations.items():
                    source_text = next((t for k, t in entries if k == key), "")
                    if source_text and english:
                        tm.store(source_text, english, req.source_lang)

                raw_responses = getattr(provider, "last_raw_responses", [])
                if raw_responses:
                    _stamp_raw_responses(raw_responses)
                    responses_path = GameStorage("chrono_ark").mod_file(req.mod_id, "last_api_responses.json")
                    responses_path.parent.mkdir(parents=True, exist_ok=True)
                    existing_responses = []
                    if not req.is_first_batch and responses_path.exists():
                        try:
                            with open(responses_path, "r", encoding="utf-8") as f:
                                existing_responses = json.load(f)
                        except Exception:
                            pass
                    existing_responses.extend(raw_responses)
                    with open(responses_path, "w", encoding="utf-8") as f:
                        json.dump(existing_responses, f, indent=2, ensure_ascii=False)

                save_translations_bulk(req.mod_id, translations)

                tracker = ProgressTracker()
                tracker.mark_translated(req.mod_id, list(translations.keys()))

                tm.save()

                filtered_suggestions = _filter_suggestions(suggestions, strings)

                # Auto-detect name-key terms not already suggested.
                existing_suggestions = load_suggestions(req.mod_id)
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
                    add_suggestions(req.mod_id, filtered_suggestions)

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
