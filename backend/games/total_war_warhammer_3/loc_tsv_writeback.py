"""Surgical writeback from `translations.json` into user `.loc.tsv` files.

Preserves the user's row ordering, blank lines, RPFM metadata header and untouched rows. An existing key has column 1 (text) replaced and the
`tooltip` column kept verbatim. A new key is appended as `key\\ttext\\ttrue`. A missing file is created with the standard header + metadata line.
"""

from __future__ import annotations

from pathlib import Path

from backend.games.total_war_warhammer_3.loc_extractor import escape_loc_text, normalize_loc_filename
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod
from backend.core.json_store import write_text_atomic


def read_loc_tsv_lines(path: Path) -> list[str]:
    """Read a `.loc.tsv` file as lines with no trailing newline.

    Args:
        path: `.loc.tsv` file.

    Returns:
        Line strings.
    """
    return path.read_text(encoding="utf-8").splitlines()


def _new_loc_tsv_skeleton(path: Path) -> list[str]:
    """Build the two-line header for a brand-new `.loc.tsv` file.

    Args:
        path: File path, used to derive the metadata line's `text/<stem>.loc`.

    Returns:
        Two-line list: `["key\\ttext\\ttooltip", "#Loc;1;text/<stem>.loc\\t\\t"]`.
    """
    stem = path.name
    if stem.endswith(".loc.tsv"):
        stem = stem[: -len(".loc.tsv")]
    elif stem.endswith(".tsv"):
        stem = stem[: -len(".tsv")]
    return ["key\ttext\ttooltip", f"#Loc;1;text/{stem}.loc\t\t"]


def apply_row_patches(path: Path, patches: dict[str, str]) -> None:
    """Surgically apply translation patches to a `.loc.tsv` file.

    An existing key has its text column replaced, with the tooltip column and the rest of the file kept verbatim.
    A new key is appended as `key<TAB>text<TAB>true`.
    A missing file is created with the standard 2-line header first.

    Args:
        path: `.loc.tsv` file to patch.
        patches: Loc key to new translated text.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = _new_loc_tsv_skeleton(path)
    else:
        lines = read_loc_tsv_lines(path)

    remaining = dict(patches)
    for i, line in enumerate(lines):
        if i < 2:
            continue
        if not line or line.startswith("#"):
            continue
        first_tab = line.find("\t")
        if first_tab < 0:
            continue
        key = line[:first_tab]
        if key in remaining:
            second_tab = line.find("\t", first_tab + 1)
            tooltip = line[second_tab + 1 :] if second_tab >= 0 else "true"
            lines[i] = f"{key}\t{escape_loc_text(remaining[key])}\t{tooltip}"
            remaining.pop(key)

    for key, text in remaining.items():
        lines.append(f"{key}\t{escape_loc_text(text)}\ttrue")

    write_text_atomic(path, "\n".join(lines) + "\n")


def remove_keys_from_loc_tsv(mod: WH3TranslationMod, keys_by_file: dict[str, set[str]]) -> dict[str, int]:
    """Delete the given keys from each user `.loc.tsv` file, keeping the two-line header.

    Prunes orphan strings (translated keys whose parent source is gone) during sync. Files missing on disk are skipped.

    Args:
        mod: Translation mod whose `.loc.tsv` files to prune.
        keys_by_file: Normalized `.loc.tsv` filename to the keys to remove.

    Returns:
        `{absolute_path: removed_count}` for each file that had rows removed.
    """
    result: dict[str, int] = {}
    for fname, keys in keys_by_file.items():
        if not keys:
            continue
        target = _find_existing_user_file(mod, fname)
        if target is None or not target.exists():
            continue
        lines = read_loc_tsv_lines(target)
        kept: list[str] = []
        removed = 0
        for i, line in enumerate(lines):
            if i < 2 or not line or line.startswith("#"):
                kept.append(line)
                continue
            first_tab = line.find("\t")
            key = line[:first_tab] if first_tab >= 0 else line
            if key in keys:
                removed += 1
                continue
            kept.append(line)
        if removed:
            write_text_atomic(target, "\n".join(kept) + "\n")
            result[str(target)] = removed
    return result


def _find_existing_user_file(mod: WH3TranslationMod, normalized_filename: str) -> Path | None:
    """Find the user's `.loc.tsv` file matching a normalized parent filename under `mod.local_source_dir/text/**`.

    Args:
        mod: Translation mod whose source dir to search.
        normalized_filename: Target name, e.g. `"def_units.loc.tsv"`.

    Returns:
        Matching path, or `None`.
    """
    text_dir = mod.local_source_dir / "text"
    if not text_dir.exists():
        return None
    for candidate in text_dir.rglob("*.loc.tsv"):
        if normalize_loc_filename(candidate.name) == normalized_filename:
            return candidate
    return None


def sync_translations_to_loc_tsv(mod: WH3TranslationMod, drift_rows: list[dict]) -> dict[str, int]:
    """Apply each drift row's `translation_text` to the matching user `.loc.tsv`.

    Rows with `translation_text is None` are skipped and the rest are grouped by `source_filename`.
    Each group goes to the user's existing matching file
    (via `_find_existing_user_file`), or to a new `<local_source_dir>/text/<mod.prefix><source_filename>` when none matches.

    Args:
        mod: Translation mod whose `.loc.tsv` files to update.
        drift_rows: Drift-row dicts from `GET /strings`, needing `source_filename`, `key` and `translation_text`.

    Returns:
        `{absolute_path: patch_count}` of keys written per file.
    """
    by_file: dict[str, dict[str, str]] = {}
    for row in drift_rows:
        text = row.get("translation_text")
        if text is None:
            continue
        fname = row["source_filename"]
        by_file.setdefault(fname, {})[row["key"]] = text

    result: dict[str, int] = {}
    for fname, patches in by_file.items():
        target = _find_existing_user_file(mod, fname)
        if target is None:
            target = mod.local_source_dir / "text" / f"{mod.prefix}{fname}"
        apply_row_patches(target, patches)
        result[str(target)] = len(patches)
    return result


__all__ = ["read_loc_tsv_lines", "apply_row_patches", "remove_keys_from_loc_tsv", "sync_translations_to_loc_tsv"]
