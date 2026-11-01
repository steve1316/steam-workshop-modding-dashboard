"""Diff WH3 translation `.loc.tsv` files against parent-mod source strings.

The drift snapshot stores SHA-256 hashes of parent text per `(filename, key)`.
A key is `stale` when the current parent hash differs from the snapshot.
Keys only in the translation are `orphan`. Keys only in the parent, or with empty translation text, are `untranslated`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from backend.games.total_war_warhammer_3.loc_extractor import LocRow

DriftStatus = Literal["translated", "untranslated", "stale", "orphan"]


@dataclass(frozen=True)
class DriftRow:
    """One row in the drift report.

    Attributes:
        source_filename: Normalized parent `.loc.tsv` filename.
        key: Localization key.
        parent_text: Current parent text, `None` for orphan rows.
        translation_text: Current translation, `None` for untranslated rows.
        status: `translated`, `untranslated`, `stale` or `orphan`.
        provider: `"claude"`, `"manual"`, or `None` when untranslated.
    """

    source_filename: str
    key: str
    parent_text: str | None
    translation_text: str | None
    status: DriftStatus
    provider: str | None = None


def hash_text(text: str) -> str:
    """Return the SHA-256 hex digest of the UTF-8 encoded `text`.

    Args:
        text: String to hash.

    Returns:
        64-character lowercase hex digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_entry(text: str) -> dict[str, str]:
    """Build a parent snapshot entry for `text`.

    Args:
        text: Parent source text to record.

    Returns:
        `{"hash": sha256_hex, "text": text}`.
    """
    return {"hash": hash_text(text), "text": text}


def entry_hash(entry: str | dict | None) -> str | None:
    """Return the recorded hash of a snapshot entry.

    Args:
        entry: `{hash, text}` dict, a legacy bare hash string, or `None`.

    Returns:
        The hash, or `None` when there is no entry.
    """
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry.get("hash")
    return entry


def entry_text(entry: str | dict | None) -> str | None:
    """Return the recorded source text of a snapshot entry.

    Args:
        entry: `{hash, text}` dict, a legacy bare hash string, or `None`.

    Returns:
        The text, or `None` for a legacy or missing entry.
    """
    return entry.get("text") if isinstance(entry, dict) else None


def compute_drift(
    *,
    parent: dict[str, dict[str, LocRow]],
    translation: dict[str, dict[str, LocRow]],
    snapshot: Mapping[str, Mapping[str, str | dict]],
) -> list[DriftRow]:
    """Compute per-row drift status.

    Args:
        parent: `{filename: {key: LocRow}}` from the parent `.pack`.
        translation: `{filename: {key: LocRow}}` from the user's translation `.loc.tsv` files.
        snapshot: `{filename: {key: entry}}` of the parent text the user last acted on, entries being `{hash, text}` or a legacy sha256 string.

    Returns:
        `DriftRow`s sorted by filename then key.
    """
    rows: list[DriftRow] = []
    all_filenames = set(parent) | set(translation)

    for filename in all_filenames:
        parent_rows = parent.get(filename, {})
        translation_rows = translation.get(filename, {})
        snapshot_for_file = snapshot.get(filename, {})

        all_keys = set(parent_rows) | set(translation_rows)
        for key in all_keys:
            p_row = parent_rows.get(key)
            t_row = translation_rows.get(key)

            if p_row is None:
                rows.append(DriftRow(filename, key, None, t_row.text if t_row else None, "orphan"))
                continue

            if t_row is None:
                rows.append(DriftRow(filename, key, p_row.text, None, "untranslated"))
                continue

            # An empty entry is a placeholder, not a translation.
            if not t_row.text:
                rows.append(DriftRow(filename, key, p_row.text, t_row.text, "untranslated"))
                continue

            current_hash = hash_text(p_row.text)
            cached_hash = entry_hash(snapshot_for_file.get(key))

            if cached_hash is None or cached_hash == current_hash:
                rows.append(DriftRow(filename, key, p_row.text, t_row.text, "translated"))
            else:
                rows.append(DriftRow(filename, key, p_row.text, t_row.text, "stale"))

    rows.sort(key=lambda r: (r.source_filename, r.key))
    return rows
