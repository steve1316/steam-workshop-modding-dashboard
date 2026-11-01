"""Map WH3 drift rows to the canonical six-state status model.

WH3's drift states plus the `translations.json` overlay fold into the shared `RowStatus`. `synced` means the effective translation already
matches the `.loc.tsv` on disk. Source drift (`stale`) becomes `changed`, an unsynced edit with no drift is `pending`, and `orphan` and `untranslated`
become `missing`. A blank parent source is `untranslatable`. WH3 has no `untouched` state.
"""

from __future__ import annotations

from backend.games.total_war_warhammer_3.translation.drift import DriftRow
from backend.translation.status import StatusRow, classify_status


def to_status_rows(drift: list[DriftRow], raw_translations: dict) -> list[StatusRow]:
    """Map drift rows plus the translations.json overlay to canonical `StatusRow`s.

    Args:
        drift: Rows from `compute_drift`.
        raw_translations: The mod's `translations.json` (`key -> {text, provider}`).

    Returns:
        One `StatusRow` per drift row, in input order.
    """
    rows: list[StatusRow] = []
    for row in drift:
        entry = raw_translations.get(row.key) or {}
        has_override = isinstance(entry, dict) and "text" in entry
        loc_text = row.translation_text or ""
        target_text = entry["text"] if has_override else row.translation_text
        has_translation = bool(target_text)

        if has_override and target_text:
            provider = entry.get("provider") or "manual"
        elif has_override:
            provider = None
        else:
            provider = "manual" if loc_text else None

        # Blank parent source has nothing to translate.
        untranslatable_reason = "Source text is empty" if row.parent_text is not None and not row.parent_text.strip() else None

        if row.status == "orphan":
            status = "missing"
        else:
            is_synced = has_translation and (target_text or "") == loc_text
            status = classify_status(
                untranslatable_reason=untranslatable_reason,
                has_translation=has_translation,
                is_synced=is_synced,
                source_changed=row.status == "stale",
            )

        rows.append(
            StatusRow(
                key=row.key,
                source_file=row.source_filename,
                source_text=row.parent_text,
                target_text=target_text,
                status=status,
                provider=provider,
                untranslatable_reason=untranslatable_reason,
            )
        )
    return rows
