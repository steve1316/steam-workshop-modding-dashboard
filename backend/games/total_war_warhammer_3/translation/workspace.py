"""A WH3 translation mod's working state: parent and local strings, the source snapshot, drift, and translations.json overlaid on top.

Extraction sits behind module-level functions so tests can monkeypatch them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from backend.core.errors import DomainError
from backend.core.settings import settings
from backend.games.total_war_warhammer_3 import GAME_ID
from backend.games.total_war_warhammer_3.loc.extractor import LocRow, extract_parent_pack_strings, normalize_loc_filename, read_translation_loc_tsv
from backend.games.total_war_warhammer_3.paths import parent_pack_cache_dir, resolve_rpfm_cli_path, rpfm_cli_candidate, tw3_workshop_content_dir
from backend.games.total_war_warhammer_3.translation.drift import DriftRow, compute_drift
from backend.games.total_war_warhammer_3.translation.mods import WH3TranslationMod
from backend.games.total_war_warhammer_3.translation.source_snapshot import load_parent_snapshot
from backend.persistence import translation_store

Strings = dict[str, dict[str, LocRow]]


class SourceUnavailableError(DomainError):
    """The parent packs cannot be read because RPFM or the Steam library is not set up."""

    status_code = 500


def extract_translation_strings(mod: WH3TranslationMod) -> Strings:
    """Read all `.loc.tsv` files under `mod.local_source_dir/text/**`.

    Args:
        mod: Translation mod whose local source dir to scan.

    Returns:
        Normalized filename to `{key: LocRow}`.
    """
    out: Strings = {}
    text_dir = mod.local_source_dir / "text"
    if not text_dir.exists():
        return out
    for tsv in text_dir.rglob("*.loc.tsv"):
        out[normalize_loc_filename(tsv.name)] = read_translation_loc_tsv(tsv)
    return out


def extract_parent_strings(mod: WH3TranslationMod) -> Strings:
    """Extract `.loc` strings from every parent `.pack` declared on `mod`.

    Args:
        mod: Translation mod whose parent packs to extract.

    Returns:
        Normalized filename to `{key: LocRow}`, merged across all parents.
    """
    rpfm = resolve_rpfm_cli_path()
    if rpfm is None:
        tried = rpfm_cli_candidate(settings.tw3.rpfm_cli_path or "", settings.tw3.helper_path or "") or "SWMT_TW3_RPFM_CLI_PATH"
        raise SourceUnavailableError(f"rpfm_cli not found (tried {tried}); set SWMT_TW3_RPFM_CLI_PATH or place rpfm_cli.exe in SWMT_TW3_HELPER_PATH")

    merged: Strings = {}
    for parent_id in mod.parent_workshop_ids:
        parent_dir = tw3_workshop_content_dir(parent_id)
        if parent_dir is None:
            raise SourceUnavailableError("TW3 Steam library drive is not configured")
        if not parent_dir.exists():
            continue
        cache_dir = parent_pack_cache_dir(parent_id)
        for pack in sorted(parent_dir.glob("*.pack")):
            for filename, rows in extract_parent_pack_strings(pack, rpfm, cache_dir).items():
                merged.setdefault(filename, {}).update(rows)
    return merged


def overlay_translations(drift: list[DriftRow], raw_translations: dict) -> list[DriftRow]:
    """Overlay `translations.json` onto computed drift rows so in-flight edits and clears show immediately.

    A non-empty override supplies its text/provider and promotes an untranslated row to `translated`. An empty-string override is an explicit clear,
    so the row shows empty text and is `untranslated` (when it has parent text) rather than the `.loc.tsv` content. Rows with no override keep their
    `.loc.tsv` status, with `provider` `manual` when text is present and `None` otherwise.

    Args:
        drift: Rows from `compute_drift`.
        raw_translations: The mod's `translations.json` (`key -> {text, provider}`).

    Returns:
        New `DriftRow` list with overrides applied, in input order.
    """
    overlaid: list[DriftRow] = []
    for row in drift:
        entry = raw_translations.get(row.key) or {}
        has_override = isinstance(entry, dict) and "text" in entry
        if has_override and entry["text"]:
            # Present in translations.json but untranslated on disk, so promote it.
            status = "translated" if row.status == "untranslated" else row.status
            overlaid.append(DriftRow(row.source_filename, row.key, row.parent_text, entry["text"], status, entry.get("provider") or "manual"))
        elif has_override:
            # Explicit clear: show empty and mark untranslated so the .loc.tsv content does not show through.
            status = "untranslated" if row.parent_text is not None else row.status
            overlaid.append(DriftRow(row.source_filename, row.key, row.parent_text, "", status, None))
        else:
            overlaid.append(DriftRow(row.source_filename, row.key, row.parent_text, row.translation_text, row.status, "manual" if row.translation_text else None))
    return overlaid


@dataclass(frozen=True)
class Workspace:
    """One read of a mod's strings, shared by every view that needs drift or the overlaid rows."""

    parent: Strings
    translation: Strings
    snapshot: dict
    drift: list[DriftRow]
    raw_translations: dict

    @cached_property
    def overlaid(self) -> list[DriftRow]:
        """Drift rows with `translations.json` applied, orphans included."""
        return overlay_translations(self.drift, self.raw_translations)

    @property
    def rows(self) -> list[DriftRow]:
        """The table's rows. Orphans (translated keys whose parent source is gone) are hidden and pruned from disk on the next Sync."""
        return [r for r in self.overlaid if r.status != "orphan"]

    def source_by_key(self) -> dict[str, str]:
        """Return each key's parent source text.

        Returns:
            Key to source text, across every parent table.
        """
        return {key: row.text for rows in self.parent.values() for key, row in rows.items()}


def load_workspace(mod: WH3TranslationMod) -> Workspace:
    """Extract a mod's strings and compute its drift against the source snapshot.

    Args:
        mod: Translation mod to load.

    Returns:
        The mod's `Workspace`.
    """
    parent = extract_parent_strings(mod)
    translation = extract_translation_strings(mod)
    snapshot = load_parent_snapshot(mod.workshop_id)
    drift = compute_drift(parent=parent, translation=translation, snapshot=snapshot)
    return Workspace(parent, translation, snapshot, drift, translation_store.load_translations_raw(mod.workshop_id, game_id=GAME_ID))
