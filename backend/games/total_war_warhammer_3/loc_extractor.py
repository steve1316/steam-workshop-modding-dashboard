"""Read `.loc.tsv` files and extract parent-pack strings via the RPFM CLI for Total War: Warhammer III mods.

RPFM exports loc tables as TSV with two header lines:
  Line 0: literal header `key\ttext\ttooltip`
  Line 1: RPFM metadata `#Loc;1;text/<filename>.loc\t\t`
Lines 2+ are data rows.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocRow:
    """One row from a `.loc.tsv` file.

    Attributes:
        key: Localization key (column 0).
        text: Translated or source text (column 1).
        tooltip: Whether this entry is shown as a tooltip (column 2).
    """

    key: str
    text: str
    tooltip: bool


def _parse_tooltip(value: str) -> bool:
    """Parse the tooltip column. Accepts `true` / `false` case-insensitively.

    Args:
        value: Raw string from the tooltip column.

    Returns:
        True if the value is `true` (case-insensitive), False otherwise.
    """
    return value.strip().lower() == "true"


def escape_loc_text(text: str) -> str:
    """Escape a translation string so it occupies a single RPFM loc TSV cell.

    A real newline or tab in the cell would break the one-row-per-entry TSV structure that `--tsv-to-binary` requires
    (continuation lines get parsed as bogus rows whose key column holds stray text). RPFM's TSV form escapes the loc
    line-break marker, so a rendered line break is stored as `\\\\n` (backslash, backslash, n) and a literal backslash as
    `\\\\`. Convert real newlines/tabs (and folded carriage returns) accordingly to match how the user's loc files - and
    RPFM's own exports - represent them.

    Args:
        text: The raw translation text (may contain real newlines, tabs, or backslashes).

    Returns:
        A single-line string safe to write as a loc TSV text cell.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "\\\\")
    return text.replace("\t", "\\\\t").replace("\n", "\\\\n")


def unescape_loc_text(text: str) -> str:
    """Inverse of `escape_loc_text`: turn RPFM loc TSV escape sequences back into real characters.

    Scans left to right so an escaped backslash pair (`\\\\`) is consumed as a unit: `\\\\n` -> newline, `\\\\t` -> tab, and a
    bare `\\\\` -> a single backslash. A lone `\\` (not doubled) is left as-is.

    Args:
        text: A loc TSV text cell as read from disk.

    Returns:
        The text with the escape sequences turned back into real newlines, tabs, and backslashes.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n and text[i + 1] == "\\":
            after = text[i + 2] if i + 2 < n else ""
            if after == "n":
                out.append("\n")
                i += 3
                continue
            if after == "t":
                out.append("\t")
                i += 3
                continue
            out.append("\\")
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def read_translation_loc_tsv(path: Path) -> dict[str, LocRow]:
    """Parse a `.loc.tsv` file into a dict keyed by loc key.

    Skips the literal header row and the RPFM `#Loc;1;...` metadata row. The `text` cell is unescaped via `unescape_loc_text`
    so callers see real newlines/tabs. Whitespace-only `text` cells are preserved verbatim.

    Args:
        path: Filesystem path to the `.loc.tsv` file.

    Returns:
        Dictionary mapping `key` to `LocRow`.

    Raises:
        FileNotFoundError: If `path` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"loc.tsv not found: {path}")

    rows: dict[str, LocRow] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for line_no, parts in enumerate(reader):
            if line_no == 0:
                continue  # header
            if not parts:
                continue
            if parts[0].startswith("#Loc"):
                continue  # RPFM metadata
            if len(parts) < 3:
                # malformed row - pad missing columns with empty strings
                parts = parts + [""] * (3 - len(parts))
            key, text, tooltip = parts[0], unescape_loc_text(parts[1]), parts[2]
            if not key:
                continue
            rows[key] = LocRow(key=key, text=text, tooltip=_parse_tooltip(tooltip))
    return rows


def normalize_loc_filename(name: str) -> str:
    """Strip leading non-alphanumeric prefix and lowercase.

    Removes RPFM load-order prefixes like `@@` and `!!!` so that translation
    and parent loc files can be matched up regardless of prefix.

    Args:
        name: The `.loc.tsv` filename (basename only).

    Returns:
        Normalized lowercase filename with leading non-alphanumeric prefix removed.
    """
    stripped = re.sub(r"^[^A-Za-z0-9]+", "", name)
    return stripped.lower()


def _pack_mtime_path(cache_dir: Path) -> Path:
    """Return the path to the cached mtime sentinel file.

    Args:
        cache_dir: The per-pack cache directory.

    Returns:
        Path to `pack_mtime.txt` inside `cache_dir`.
    """
    return cache_dir / "pack_mtime.txt"


def _extracted_dir(cache_dir: Path) -> Path:
    """Return the directory where RPFM writes extracted TSV files.

    Args:
        cache_dir: The per-pack cache directory.

    Returns:
        Path to the `extracted` subdirectory inside `cache_dir`.
    """
    return cache_dir / "extracted"


def _read_cached_mtime(cache_dir: Path) -> int | None:
    """Read the previously-recorded pack mtime from disk.

    Args:
        cache_dir: The per-pack cache directory.

    Returns:
        The cached mtime as an integer, or None if unavailable.
    """
    p = _pack_mtime_path(cache_dir)
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _read_all_extracted(cache_dir: Path) -> dict[str, dict[str, LocRow]]:
    """Parse every `.loc.tsv` file in the extracted subdirectory.

    Args:
        cache_dir: The per-pack cache directory.

    Returns:
        Dictionary mapping normalized loc filename to its parsed rows.
    """
    out: dict[str, dict[str, LocRow]] = {}
    extracted = _extracted_dir(cache_dir)
    if not extracted.exists():
        return out
    for tsv in extracted.rglob("*.loc.tsv"):
        out[normalize_loc_filename(tsv.name)] = read_translation_loc_tsv(tsv)
    return out


def extract_parent_pack_strings(
    pack_path: Path,
    rpfm_cli_path: Path,
    cache_dir: Path,
) -> dict[str, dict[str, LocRow]]:
    """Extract all `.loc` tables from a binary `.pack` via RPFM CLI.

    Re-extracts only when the source `.pack` mtime differs from the cached
    mtime. Otherwise returns the previously-extracted TSVs from disk.

    Args:
        pack_path: Absolute path to the parent `.pack` file.
        rpfm_cli_path: Absolute path to the `rpfm_cli` executable.
        cache_dir: Per-parent-mod cache directory. Created if absent.

    Returns:
        `{normalized_loc_filename: {loc_key: LocRow}}`.

    Raises:
        FileNotFoundError: If `pack_path` does not exist.
        RuntimeError: If the RPFM CLI subprocess returns a non-zero exit code.
    """
    if not pack_path.exists():
        raise FileNotFoundError(f"pack not found: {pack_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    current_mtime = int(pack_path.stat().st_mtime)
    cached_mtime = _read_cached_mtime(cache_dir)

    if cached_mtime == current_mtime and _extracted_dir(cache_dir).exists():
        return _read_all_extracted(cache_dir)

    # Start from an empty folder so loc files removed from the pack do not linger from an earlier extract.
    extracted = _extracted_dir(cache_dir)
    shutil.rmtree(extracted, ignore_errors=True)
    extracted.mkdir(parents=True, exist_ok=True)

    # Locate the schema next to rpfm_cli.exe so .loc tables decode into TSV during extract.
    schema_path = rpfm_cli_path.parent / "schemas" / "schema_wh3.ron"

    cmd = [
        str(rpfm_cli_path),
        "--game",
        "warhammer_3",
        "pack",
        "extract",
        "--pack-path",
        str(pack_path),
        "--tables-as-tsv",
        str(schema_path),
        "--folder-path",
        f"text;{extracted}",
    ]
    result = subprocess.run(cmd, capture_output=True, cwd=str(rpfm_cli_path.parent))
    if result.returncode != 0:
        raise RuntimeError(f"RPFM CLI failed (exit {result.returncode}): {result.stderr.decode('utf-8', errors='replace')}")

    _pack_mtime_path(cache_dir).write_text(str(current_mtime), encoding="utf-8")
    return _read_all_extracted(cache_dir)
