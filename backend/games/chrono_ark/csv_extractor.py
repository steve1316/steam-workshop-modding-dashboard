"""CSV extractor: parses the base game's Lang*.csv and mod Localization/*.csv files into `LocString`."""

import csv
import re
from pathlib import Path

from backend.models.loc import LocString

_CANONICAL_NAMES = {"LangDataDB.csv", "LangSystemDB.csv", "LangDialogueDB.csv", "LangRecordsDB.csv"}

# Directory names that indicate backups. The Chinese entries mean "backup".
_BACKUP_DIR_PATTERNS = {"langbackup", "备份", "备份2", "备份3", "备份4", "备份5"}

# Strips variant suffixes from filenames.
_VARIANT_SUFFIX_RE = re.compile(
    r"( - 副本"  # Chinese "copy"
    r"| \(\d+\)"  # " (1)", " (2)"
    r"|（\d+）"  # fullwidth parens
    r"|_v[\d.]+"  # "_v0.6.13"
    r"|_copy"  # "_copy"
    r"| copy"  # " copy"
    r")(?=\.csv$)",
    re.IGNORECASE,
)


def _fix_oversized_row(row: list[str], expected_cols: int, col_indices: dict[str, int]) -> list[str]:
    """Re-merge the excess columns of a row split by unquoted commas.

    Tries the merge at each language-column position and keeps the one whose cells best match their column's script.

    Args:
        row: Parsed row with too many columns.
        expected_cols: Column count from the header.
        col_indices: `{column name: index}`.

    Returns:
        Corrected row, or the original if no merge candidate is valid.
    """
    excess = len(row) - expected_cols
    if excess <= 0:
        return row

    language_columns = {"Korean", "English", "Japanese", "Chinese", "Chinese-TW [zh-tw]"}
    lang_positions = sorted(idx for lang, idx in col_indices.items() if lang in language_columns)
    if not lang_positions:
        return row

    best_row = None
    best_score = -1

    for merge_pos in lang_positions:
        end = merge_pos + excess + 1
        if end > len(row):
            continue
        candidate = row[:merge_pos] + [",".join(row[merge_pos:end])] + row[end:]

        score = 0
        for lang, idx in col_indices.items():
            if lang not in language_columns or idx >= len(candidate):
                continue
            cell = candidate[idx].strip()
            if not cell:
                continue
            has_hangul = any("\uac00" <= c <= "\ud7af" for c in cell)
            has_kana = any("\u3040" <= c <= "\u30ff" for c in cell)
            has_cjk = any("\u4e00" <= c <= "\u9fff" for c in cell)
            ascii_ratio = sum(1 for c in cell if ord(c) < 128) / len(cell)

            if lang == "English":
                if ascii_ratio > 0.8:
                    score += 2
                if has_hangul or has_kana:
                    score -= 2
            elif lang == "Korean":
                if has_hangul:
                    score += 1
                if ascii_ratio > 0.9 and len(cell) > 10:
                    score -= 1
            elif lang == "Japanese":
                if has_kana:
                    score += 1
            elif lang in ("Chinese", "Chinese-TW [zh-tw]"):
                if has_cjk and not has_hangul and not has_kana:
                    score += 1

        if score > best_score:
            best_score = score
            best_row = candidate

    return best_row if best_row is not None else row


def _is_valid_key(key: str) -> bool:
    """Check whether a string looks like a localization key.

    Args:
        key: String to validate.

    Returns:
        True if it only has alphanumerics, `_`, `-`, `.` and `/`.
    """
    if not key or " " in key:
        return False
    # Multi-byte characters or spaces mean it's probably text, not a key.
    return bool(re.match(r"^[A-Za-z0-9_\-\./]+$", key))


def _drop_redundant_desc_keys(strings: dict[str, LocString]) -> dict[str, LocString]:
    """Drop the shorter of `_Desc`/`_Description` and `_PassiveDes`/`_PassiveDesc` pairs, which carry identical values.

    Args:
        strings: Localization strings, modified in place.

    Returns:
        The same dict with redundant keys removed.
    """
    to_remove = []
    for key in strings:
        if key.endswith("_Desc"):
            if key[:-5] + "_Description" in strings:
                to_remove.append(key)
        elif key.endswith("_PassiveDes"):
            if key[:-11] + "_PassiveDesc" in strings:
                to_remove.append(key)
    for key in to_remove:
        del strings[key]
    return strings


def _parse_csv_content(file_path: Path) -> list[LocString]:
    """Parse a localization CSV, stitching unquoted multiline strings.

    Rows that don't start with a valid key are merged into the previous entry.

    Args:
        file_path: CSV to parse.

    Returns:
        Parsed entries.
    """
    # Keys may include accented Latin letters (pinyin diacritics, U+00C0-U+024F). A slash is not required because some mods use flat keys
    # like `B_Poca_Level_State_0`. Spaces are only allowed after a slash (e.g. `Character/Suzakuin Momiji_name`).
    _LATIN = r"A-Za-z0-9\u00C0-\u024F"
    key_pattern = re.compile(rf"^[{_LATIN}_\-\.][{_LATIN}_\-\./]*(?:/[{_LATIN}_\-\./ ]+)?$")

    results = []

    try:
        f = open(file_path, encoding="utf-8-sig", newline="")
        reader = csv.reader(f)
    except Exception as e:
        print(f"Error opening CSV {file_path}: {e}")
        return results

    try:
        header = next(reader)
    except StopIteration:
        return results

    header = [h.strip().rstrip("\r") for h in header]
    col_indices = {col_name: i for i, col_name in enumerate(header)}

    language_columns = ["Korean", "English", "Japanese", "Chinese", "Chinese-TW [zh-tw]"]
    active_langs = [lang for lang in language_columns if lang in col_indices]

    last_entry: LocString | None = None
    # Column the last entry was populating, for continuation ("zombie") rows.
    current_col_offset = 0

    for row in reader:
        if not row:
            continue

        if len(row) > len(header):
            row = _fix_oversized_row(row, len(header), col_indices)

        first_cell = row[0].strip()

        # A continuation has an invalid key, or is a short row belonging to the previous entry's description.
        is_continuation = last_entry is not None and (
            not first_cell
            or not key_pattern.match(first_cell)
            or
            # If it's a known key pattern but the row is too short to be a real record
            (len(row) < 3 and last_entry)
        )

        if is_continuation and last_entry is not None:
            # Append from `current_col_offset` (or 3 = Korean) onward.
            for i, val in enumerate(row):
                target_idx = current_col_offset + i

                target_lang = None
                for lang, idx in col_indices.items():
                    if idx == target_idx and lang in language_columns:
                        target_lang = lang
                        break

                if target_lang:
                    old_val = last_entry.translations.get(target_lang, "")
                    last_entry.translations[target_lang] = (old_val + "\n" + val).strip()
                elif target_idx == col_indices.get("Desc"):
                    last_entry.desc = (last_entry.desc + "\n" + val).strip()
            current_col_offset = min(current_col_offset + len(row) - 1, len(header) - 1)
            continue

        key = first_cell
        if not key:
            continue

        # DLL orphan keys from a prior export are untranslatable and must only come from the DLL orphan pass (which sets untranslatable_reason).
        if key.startswith("DLL/"):
            continue

        entry_type = row[col_indices["Type"]].strip() if "Type" in col_indices and col_indices["Type"] < len(row) else ""
        desc = row[col_indices["Desc"]].strip() if "Desc" in col_indices and col_indices["Desc"] < len(row) else ""

        translations = {}
        max_idx = 0
        for lang in active_langs:
            idx = col_indices[lang]
            if idx < len(row):
                text = row[idx].strip()
                if text:
                    translations[lang] = text
                    max_idx = max(max_idx, idx)

        loc_string = LocString(
            key=key,
            type=entry_type,
            desc=desc,
            translations=translations,
            source_file=file_path.name,
        )
        results.append(loc_string)
        last_entry = loc_string
        # A short row's continuation lines resume at the last filled column.
        current_col_offset = max_idx if len(row) < len(header) else 3  # Default to Korean

    return results


def extract_base_game_strings(
    base_game_path: Path,
    csv_files: list[str],
) -> dict[str, LocString]:
    """Extract all localization strings from the base game's CSV files.

    Args:
        base_game_path: StreamingAssets directory.
        csv_files: CSV filenames to parse.

    Returns:
        `{key: LocString}`.
    """
    all_strings: dict[str, LocString] = {}

    for csv_filename in csv_files:
        csv_path = base_game_path / csv_filename
        if not csv_path.exists():
            print(f"  Warning: {csv_filename} not found at {csv_path}")
            continue

        entries = _parse_csv_content(csv_path)
        for entry in entries:
            all_strings[entry.key] = entry

        print(f"  Parsed {csv_filename}: {len(entries)} entries")

    _drop_redundant_desc_keys(all_strings)
    print(f"  Total base game strings: {len(all_strings)}")
    return all_strings


def find_all_csv_files(mod_path: Path) -> list[Path]:
    """Find a mod's CSVs: Localization/, top-level Lang*.csv, and backup-directory variants.

    Args:
        mod_path: Mod root directory.

    Returns:
        All discovered CSV paths.
    """
    found = []
    loc_dir = mod_path / "Localization"

    # Localization/ top level only, nested folders are skipped.
    if loc_dir.exists():
        for csv_file in loc_dir.glob("*.csv"):
            found.append(csv_file)

    for csv_file in mod_path.glob("Lang*.csv"):
        if csv_file not in found:
            found.append(csv_file)

    for subdir in mod_path.iterdir():
        if subdir.is_dir() and subdir.name != "Localization":
            dir_lower = subdir.name.lower()
            is_backup = any(p in dir_lower for p in _BACKUP_DIR_PATTERNS)
            if is_backup:
                for csv_file in subdir.rglob("*.csv"):
                    if csv_file not in found:
                        found.append(csv_file)

    return found


def classify_csv_file(csv_path: Path, loc_dir: Path) -> tuple[str, bool]:
    """Classify a CSV as canonical or variant and find its canonical name.

    Args:
        csv_path: CSV file.
        loc_dir: Localization/ directory (or mod root).

    Returns:
        `(canonical_filename, is_canonical)`.
    """
    filename = csv_path.name

    in_backup = False
    for part in csv_path.parts:
        part_lower = part.lower()
        if any(p in part_lower for p in _BACKUP_DIR_PATTERNS):
            in_backup = True
            break

    canonical = _VARIANT_SUFFIX_RE.sub("", filename)

    is_canonical = canonical == filename and not in_backup and canonical in _CANONICAL_NAMES

    # Top-level file when Localization/ version exists is a variant.
    if is_canonical and csv_path.parent != loc_dir:
        loc_version = loc_dir / canonical
        if loc_version.exists() and csv_path != loc_version:
            is_canonical = False

    return canonical, is_canonical


def extract_mod_strings(mod_path: Path) -> tuple[dict[str, LocString], list[str]]:
    """Extract strings from all of a mod's CSVs, deduplicated by key with canonical files winning.

    Args:
        mod_path: Mod root directory.

    Returns:
        `(strings, variant file relative paths)`.
    """
    all_csv_files = find_all_csv_files(mod_path)
    if not all_csv_files:
        return {}, []

    loc_dir = mod_path / "Localization"
    if not loc_dir.exists():
        loc_dir = mod_path

    canonical_files: list[Path] = []
    variant_files: list[Path] = []

    for csv_file in all_csv_files:
        _, is_canonical = classify_csv_file(csv_file, loc_dir)
        if is_canonical:
            canonical_files.append(csv_file)
        else:
            variant_files.append(csv_file)

    # Parse variants first so canonical can overwrite on collision.
    all_strings: dict[str, LocString] = {}

    for csv_file in variant_files:
        entries = _parse_csv_content(csv_file)
        for entry in entries:
            if entry.key not in all_strings:
                all_strings[entry.key] = entry

    for csv_file in canonical_files:
        entries = _parse_csv_content(csv_file)
        for entry in entries:
            all_strings[entry.key] = entry

    variant_rel_paths = []
    for v in variant_files:
        try:
            variant_rel_paths.append(str(v.relative_to(mod_path)))
        except ValueError:
            variant_rel_paths.append(str(v))

    _drop_redundant_desc_keys(all_strings)
    return all_strings, variant_rel_paths


def detect_source_language(
    loc_string: LocString,
    source_languages: list[str],
) -> str | None:
    """Return the first source language with text.

    Args:
        loc_string: String to check.
        source_languages: Languages in priority order.

    Returns:
        Language name, or None.
    """
    for lang in source_languages:
        if lang in loc_string.translations and loc_string.translations[lang]:
            return lang
    return None


def get_untranslated_strings(
    strings: dict[str, LocString],
    source_languages: list[str],
    target_lang: str = "English",
) -> dict[str, LocString]:
    """Keep entries with an empty `target_lang` column but some source-language text.

    Args:
        strings: All localization strings.
        source_languages: Languages in priority order.
        target_lang: Language column that counts as translated.

    Returns:
        Strings needing translation.
    """
    untranslated = {}
    for key, loc_str in strings.items():
        if loc_str.untranslatable_reason and not key.startswith("DLL/"):
            continue
        translated = loc_str.translations.get(target_lang, "").strip()
        if not translated and detect_source_language(loc_str, source_languages) is not None:
            untranslated[key] = loc_str
    return untranslated
