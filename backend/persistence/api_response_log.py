"""Per-mod log of LLM API calls, bounded to the last `MAX_ENTRIES` calls.

Stored as a JSON array (newest last on disk), and `list_entries` returns newest first.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path

MAX_ENTRIES = 50


def _path(mod_id: str, game_id: str) -> Path:
    return mods_path(game_id) / mod_id / "api_responses.json"


def _load(mod_id: str, game_id: str) -> list[dict]:
    p = _path(mod_id, game_id)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def append(mod_id: str, entry: dict, *, game_id: str) -> None:
    """Append one API call entry to the mod's log, dropping the oldest past `MAX_ENTRIES`.

    Args:
        mod_id: Mod's Workshop id.
        entry: Log entry dict.
        game_id: Game the mod belongs to.
    """
    entries = _load(mod_id, game_id)
    entries.append(entry)
    p = _path(mod_id, game_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json(p, entries[-MAX_ENTRIES:])


def list_entries(mod_id: str, *, game_id: str) -> list[dict]:
    """List a mod's API call entries, newest first.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.

    Returns:
        Log entries, empty if no log exists.
    """
    return list(reversed(_load(mod_id, game_id)))


def provider_call_fields(raw_responses: list[dict], error: str | None = None) -> dict:
    """Summarize a provider's raw responses into the model, usage, cost and raw-text fields of a log entry.

    A batch split after a truncated reply has several raw responses, so usage and cost are summed and the text joined.

    Args:
        raw_responses: Provider's `last_raw_responses` records for one batch.
        error: Error message that leads the raw text when the call failed.

    Returns:
        Dict with `model`, `input_tokens`, `output_tokens`, `cost_usd` and `raw_response`.
    """

    def total(field: str):
        values = [r.get(field) for r in raw_responses]
        known = [v for v in values if v is not None]
        return sum(known) if values and len(known) == len(values) else None

    texts = [r.get("raw_text") or "" for r in raw_responses]
    if len(texts) > 1:
        texts = [f"--- Response {i + 1} (stop_reason: {r.get('stop_reason')}) ---\n{t}" for i, (r, t) in enumerate(zip(raw_responses, texts, strict=True))]
    if error:
        texts.insert(0, f"ERROR: {error}")
    return {
        "model": raw_responses[0].get("model", "claude") if raw_responses else "claude",
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "cost_usd": total("cost_usd"),
        "raw_response": "\n\n".join(texts),
    }


def log_batch_call(mod_id: str, *, game_id: str, provider: str, keys: list[str], raw_responses: list[dict], error: str | None = None) -> None:
    """Record one translate-batch provider call, with the provider's raw reply text.

    Args:
        mod_id: Mod's Workshop id.
        game_id: Game the mod belongs to.
        provider: Provider id that ran the batch.
        keys: Keys sent.
        raw_responses: Provider's raw response records for this batch.
        error: Error message when the call failed.
    """
    entry = {"timestamp": datetime.now(UTC).isoformat(), "kind": "translate-batch", "provider": provider, **provider_call_fields(raw_responses, error=error), "keys_or_inputs": keys}
    append(mod_id, entry, game_id=game_id)
