"""Append-only audit log of LLM API calls per WH3 mod.

Records translate-batch, scan-terms, and suggest-edits Claude calls. Bounded to the last 20 entries per mod; oldest is dropped when the 21st is written.
The log is stored as a JSON array (newest last on disk, but `list_entries` returns newest first for UI convenience).
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.games.storage_paths import game_storage_path
from backend.core.json_store import write_json

GAME_ID = "total_war_warhammer_3"
MAX_ENTRIES = 20


def _path(mod_id: str) -> Path:
    return game_storage_path(GAME_ID) / "mods" / mod_id / "api_responses.json"


def _load(mod_id: str) -> list[dict]:
    p = _path(mod_id)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(mod_id: str, entries: list[dict]) -> None:
    p = _path(mod_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json(p, entries)


def append(mod_id: str, entry: dict) -> None:
    """Append one API response entry to the mod's log.

    Args:
        mod_id: Steam Workshop ID of the WH3 translation mod.
        entry: Audit entry dict (timestamp, kind, provider, model, tokens, cost, keys_or_inputs, raw_response).
    """
    entries = _load(mod_id)
    entries.append(entry)
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    _save(mod_id, entries)


def list_entries(mod_id: str) -> list[dict]:
    """List API response entries for a mod, newest first.

    Args:
        mod_id: Steam Workshop ID of the WH3 translation mod.

    Returns:
        List of audit entries; empty if no log exists.
    """
    return list(reversed(_load(mod_id)))


def provider_call_fields(raw_responses: list[dict], error: str | None = None) -> dict:
    """Summarize a provider's raw responses into the model, usage, cost, and raw-text fields of a log entry.

    A batch Claude split after a truncated reply has several raw responses. Their usage and cost are summed and their text joined.

    Args:
        raw_responses: The provider's `last_raw_responses` records for one batch.
        error: Error message when the call failed. It leads the raw text so the log shows why the batch produced nothing.

    Returns:
        Dict with `model`, `input_tokens`, `output_tokens`, `cost_usd`, and `raw_response`.
    """

    def total(field: str):
        values = [r.get(field) for r in raw_responses]
        return sum(values) if values and all(v is not None for v in values) else None

    texts = [r.get("raw_text") or "" for r in raw_responses]
    if len(texts) > 1:
        texts = [f"--- Response {i + 1} (stop_reason: {r.get('stop_reason')}) ---\n{t}" for i, (r, t) in enumerate(zip(raw_responses, texts))]
    if error:
        texts.insert(0, f"ERROR: {error}")
    return {
        "model": raw_responses[0].get("model", "claude") if raw_responses else "claude",
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "cost_usd": total("cost_usd"),
        "raw_response": "\n\n".join(texts),
    }
