"""Server-sent-event streaming and cancellation of one translate batch, shared by every game's `/translate/batch/stream` and `/translate/cancel`."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import StreamingResponse

from backend.translation.pipeline import BatchJob, record_batch

_active: dict[tuple[str, str], threading.Event] = {}
"""Cancel events of the batches streaming right now, keyed by (game_id, mod_id)."""


def cancel_batch(game_id: str, mod_id: str) -> bool:
    """Signal a mod's streaming batch to stop.

    Args:
        game_id: Game the mod belongs to.
        mod_id: Mod's Workshop id.

    Returns:
        True when a batch was streaming and got the signal.
    """
    event = _active.pop((game_id, mod_id), None)
    if event:
        event.set()
    return event is not None


def stream_batch(job: BatchJob, request: Request) -> StreamingResponse:
    """Run a batch through the provider's streaming call and relay its events as SSE, persisting the `complete` event like `/translate/batch`.

    Providers without streaming yield a single `complete` event.

    Args:
        job: The batch.
        request: Incoming request, polled so a closed tab stops the provider early.

    Returns:
        The `text/event-stream` response.
    """
    return StreamingResponse(_events(job, request), media_type="text/event-stream")


async def _events(job: BatchJob, request: Request) -> AsyncIterator[str]:
    """Yield the batch's events as SSE `data:` lines.

    Args:
        job: The batch.
        request: Incoming request, polled for a disconnect.

    Returns:
        The SSE lines.
    """
    key = (job.game_id, job.mod_id)
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    loop = asyncio.get_event_loop()
    cancel_event = threading.Event()
    _active[key] = cancel_event

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
            # A newer batch for the same mod may have registered its own event, which must stay cancellable.
            if _active.get(key) is cancel_event:
                _active.pop(key, None)
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
