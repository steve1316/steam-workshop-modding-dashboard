"""Six-state `RowStatus`, the shared `classify_status()` rules, and the `StatusRow` model for the strings table."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

RowStatus = Literal["synced", "untouched", "pending", "changed", "missing", "untranslatable"]


def classify_status(
    *,
    untranslatable_reason: Optional[str] = None,
    has_translation: bool = False,
    is_synced: bool = False,
    is_untouched: bool = False,
    source_changed: bool = False,
) -> RowStatus:
    """Map a row's flags to the canonical status.

    Priority: untranslatable reason, then translated with source drift ('changed', which also covers WH3 'stale'), synced, untouched, pending,
    missing. WH3 'orphan' rows are mapped to 'missing' by the adapter before this is called.

    Args:
        untranslatable_reason: Non-empty when the row cannot be translated.
        has_translation: Row has target-language text.
        is_synced: Translation was written to the game's real files.
        is_untouched: Target text shipped with the mod and was never edited.
        source_changed: Source text drifted since the last sync/translate.

    Returns:
        The `RowStatus`.
    """
    if untranslatable_reason:
        return "untranslatable"
    if has_translation and source_changed:
        return "changed"
    if is_synced:
        return "synced"
    if is_untouched:
        return "untouched"
    if has_translation:
        return "pending"
    return "missing"


class StatusRow(BaseModel):
    """One row in the unified strings table, shared by all games."""

    key: str
    source_file: str = ""
    source_text: Optional[str] = None
    target_text: Optional[str] = None
    status: RowStatus
    provider: Optional[str] = None
    original_target: Optional[str] = None
    untranslatable_reason: Optional[str] = None
