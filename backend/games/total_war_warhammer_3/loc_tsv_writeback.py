"""Surgical writeback from `translations.json` into user `.loc.tsv` files.

The strategy preserves the user's existing row ordering, blank lines, RPFM
metadata header, and any rows we don't have translations for. For each
`(key, text)` patch:
  * If the key already exists in the file, replace column 1 (the text column)
    on its row. Column 2 (`tooltip`) is preserved verbatim.
  * If the key is new, append a row `key\\ttext\\ttrue` at the end.
If the target file does not exist, create it with the standard header +
RPFM metadata line, then append rows.
"""

from __future__ import annotations

from pathlib import Path

from backend.games.total_war_warhammer_3.loc_extractor import escape_loc_text, normalize_loc_filename
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod
from backend.core.json_store import write_text_atomic


def read_loc_tsv_lines(path: Path) -> list[str]:
    """Read a `.loc.tsv` file as a list of lines (no trailing newline).

    Args:
        path: Filesystem path to the `.loc.tsv` file.

    Returns:
        List of line strings.
    """
    return path.read_text(encoding="utf-8").splitlines()


def _new_loc_tsv_skeleton(path: Path) -> list[str]:
    """Build the two-line header for a brand-new `.loc.tsv` file.

    Args:
        path: Filesystem path the file will be written to. Used to derive the
            RPFM metadata line's `text/<stem>.loc` reference.

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

    For each `(key, new_text)` in `patches`:
      * If `key` already exists in the file, replace column 1 (text) on that
        row, preserving column 2 (tooltip) and the rest of the file verbatim.
      * Otherwise, append `key\\t<new_text>\\ttrue` at the end.

    If the file does not exist, it is created with the standard 2-line header
    before patches are appended.

    Args:
        path: Filesystem path to the `.loc.tsv` file to patch.
        patches: Mapping of loc key to new translated text.
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
    """Delete the given keys from each user `.loc.tsv` file, rewriting it without those rows.

    Used to prune orphan strings (translated keys whose parent source no longer exists) during sync. Rows are matched by their key (column 0); the
    two-line header is always preserved. Files that do not exist on disk are skipped.

    Args:
        mod: The translation mod whose `.loc.tsv` files to prune.
        keys_by_file: Mapping of normalized `.loc.tsv` filename to the set of keys to remove from it.

    Returns:
        Mapping `{absolute_path: removed_count}` for each file that actually had rows removed.
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
    """Find the user's `.loc.tsv` file that maps to a normalized parent filename.

    Walks `mod.local_source_dir/text/**` looking for any `.loc.tsv` whose
    `normalize_loc_filename(name)` matches.

    Args:
        mod: The translation mod whose source dir to search.
        normalized_filename: The target normalized filename, e.g. `"def_units.loc.tsv"`.

    Returns:
        Path to the matching file if found; otherwise `None`.
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

    Drift rows with `translation_text is None` are skipped. Rows are grouped by `source_filename`. Each group is applied to either the user's existing
    matching file (resolved via `_find_existing_user_file`) or a new file created at `<local_source_dir>/text/<mod.prefix><source_filename>` when no
    match exists.

    Args:
        mod: The translation mod whose `.loc.tsv` files to update.
        drift_rows: List of drift-row dicts (as returned by `GET /strings`). Each row needs at minimum `source_filename`, `key`, `translation_text`.

    Returns:
        Mapping `{absolute_path: patch_count}` describing how many keys were written to each file.
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
