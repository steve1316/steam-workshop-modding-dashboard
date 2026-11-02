"""DLL string extractor: reads the .NET #US (User Strings) heap via dotnetfile, and finds `ldstr` key/value pairs in IL."""

import hashlib
import re
import struct
from pathlib import Path

from backend.models.loc import LocString
from backend.text_utils import has_cjk as _has_cjk


def _detect_cjk_language(text: str) -> str:
    """Detect a CJK string's language by script: kana is Japanese, hangul is Korean, ideographs only is Chinese.

    Args:
        text: CJK string to classify.

    Returns:
        `"Japanese"`, `"Korean"`, or `"Chinese"`.
    """
    for c in text:
        if "\u3040" <= c <= "\u30ff":
            return "Japanese"
        if "\uac00" <= c <= "\ud7af":
            return "Korean"
    return "Chinese"


def _load_dotnet_pe(dll_path: Path):
    """Load a .NET PE file.

    Args:
        dll_path: .NET DLL.

    Returns:
        `DotNetPE`, or None if dotnetfile is missing or the file can't be parsed.
    """
    try:
        from dotnetfile import DotNetPE
    except ImportError:
        print("  Error: dotnetfile is not installed. Run: pip install dotnetfile")
        return None

    try:
        return DotNetPE(str(dll_path))
    except Exception as e:
        print(f"  Error reading {dll_path.name}: {e}")
        return None


def _build_us_heap_map(dotnet_file) -> dict[int, str]:
    """Map each #US heap offset to its decoded, stripped string.

    Args:
        dotnet_file: `DotNetPE` with user string lookup support.

    Returns:
        `{offset: string}`, excluding blank strings.
    """
    us_map: dict[int, str] = {}
    lookup = getattr(dotnet_file, "dotnet_user_string_lookup", None)
    if not lookup:
        return us_map
    for offset in lookup.keys():
        try:
            text = dotnet_file.get_user_string(offset)
            if text and isinstance(text, str) and text.strip():
                us_map[offset] = text.strip()
        except Exception:
            continue
    return us_map


def _is_loc_key(s: str) -> bool:
    """Check whether a string looks like a localization key.

    Args:
        s: String to check.

    Returns:
        True if it has no spaces and only alphanumerics, `_`, `-`, `.` and `/`.
    """
    if not s or " " in s:
        return False
    return bool(re.match(r"^[A-Za-z0-9_\-\./]+$", s))


def extract_dll_strings(dll_path: Path) -> list[str]:
    """Extract all user strings from a .NET assembly's #US heap.

    Args:
        dll_path: .NET DLL.

    Returns:
        Extracted strings.
    """
    dotnet_file = _load_dotnet_pe(dll_path)
    if not dotnet_file:
        return []

    us_map = _build_us_heap_map(dotnet_file)
    return list(us_map.values())


def extract_dll_loc_strings(
    dll_path: Path,
    source_file_label: str = "",
) -> dict[str, LocString]:
    """Extract localization key/value pairs from consecutive `ldstr` opcodes (0x72) in the raw DLL bytes.

    An ASCII key next to a CJK value is treated as a registration call like `AddText(key, value)` or `AddText(value, key)`.

    Args:
        dll_path: .NET DLL.
        source_file_label: Value for `LocString.source_file`.

    Returns:
        `{key: LocString}`.
    """
    dotnet_file = _load_dotnet_pe(dll_path)
    if not dotnet_file:
        return {}

    us_map = _build_us_heap_map(dotnet_file)
    if not us_map:
        return {}

    # A 0x70 table byte in the token marks a #US heap reference.
    data = dll_path.read_bytes()
    ldstr_hits: list[tuple[int, int, str]] = []  # (byte_pos, us_offset, text)

    for i in range(len(data) - 4):
        if data[i] == 0x72:
            token = struct.unpack_from("<I", data, i + 1)[0]
            if (token >> 24) == 0x70:
                us_offset = token & 0x00FFFFFF
                if us_offset in us_map:
                    ldstr_hits.append((i, us_offset, us_map[us_offset]))

    # A gap of 5 bytes means back-to-back ldstr instructions.
    results: dict[str, LocString] = {}
    MAX_GAP = 10  # Allow small gap for optional opcodes between two ldstr.

    for idx in range(len(ldstr_hits) - 1):
        pos1, _, str1 = ldstr_hits[idx]
        pos2, _, str2 = ldstr_hits[idx + 1]
        if pos2 - pos1 > MAX_GAP:
            continue

        key: str | None = None
        value: str | None = None

        if _is_loc_key(str1) and _has_cjk(str2):
            key, value = str1, str2
        elif _has_cjk(str1) and _is_loc_key(str2):
            key, value = str2, str1
        else:
            continue

        # Skip asset paths, prefab names and image references.
        if key.endswith((".prefab", ".asset", ".png", ".jpg")):
            continue
        if "/" in key and not key.startswith("Text"):
            continue

        if key not in results:
            results[key] = LocString(
                key=key,
                type="Text",
                desc="",
                translations={_detect_cjk_language(value): value},
                source_file=source_file_label,
            )

    return results


def extract_dll_orphan_strings(
    dll_path: Path,
    paired_values: set[str],
    source_file_label: str = "",
    min_string_length: int = 4,
) -> dict[str, LocString]:
    """Extract CJK strings that have no localization key and give them deterministic hash-based keys.

    Some mods (e.g. 2959784510 / Amethyst) set text via C# property assignments instead of registration calls, leaving CJK strings in the #US heap
    with no ASCII key.

    Args:
        dll_path: .NET DLL.
        paired_values: CJK values already captured by `extract_dll_loc_strings`, excluded here.
        source_file_label: Value for `LocString.source_file`.
        min_string_length: Minimum string length to consider.

    Returns:
        `{DLL/{stem}/{hash8}: LocString}`.
    """
    dotnet_file = _load_dotnet_pe(dll_path)
    if not dotnet_file:
        return {}

    us_map = _build_us_heap_map(dotnet_file)
    if not us_map:
        return {}

    stem = dll_path.stem
    results: dict[str, LocString] = {}

    for text in us_map.values():
        if not _has_cjk(text):
            continue
        if _is_noise_string(text, min_string_length):
            continue
        if text in paired_values:
            continue

        hash8 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        key = f"DLL/{stem}/{hash8}"
        if key not in results:
            results[key] = LocString(
                key=key,
                type="Text",
                desc="",
                translations={_detect_cjk_language(text): text},
                source_file=source_file_label,
                untranslatable_reason=(
                    "Hardcoded in the mod's compiled DLL. The game only"
                    " recognizes localization keys registered through its API,"
                    " so this text cannot be replaced via CSV translation."
                    " The mod author would need to externalize it."
                ),
            )

    return results


def _is_noise_string(s: str, min_string_length: int) -> bool:
    """Check whether a string is likely .NET metadata noise rather than user-facing text.

    Args:
        s: String to check.
        min_string_length: Minimum meaningful length.

    Returns:
        True if it should be filtered out.
    """
    if len(s) < min_string_length:
        return True

    # File paths and URLs.
    if "/" in s and "." in s and " " not in s:
        return True
    if s.startswith("http://") or s.startswith("https://"):
        return True
    if "\\" in s and "." in s:
        return True

    # Namespaces and type references (dot-separated PascalCase).
    if re.match(r"^[A-Z][a-zA-Z0-9]+(\.[A-Z][a-zA-Z0-9]+)+$", s):
        return True

    # Likely class/method names.
    if re.match(r"^[A-Z][a-zA-Z0-9]+$", s) and " " not in s:
        return True

    if re.match(r"^\d+\.\d+(\.\d+)*$", s):
        return True

    if len(set(s)) <= 1:
        return True

    if s in ("{0}", "{1}", "{0} {1}", "null", "true", "false"):
        return True

    return False


def filter_localizable_strings(
    strings: list[str],
    min_string_length: int,
) -> list[str]:
    """Drop .NET noise (type names, paths, format strings) from extracted DLL strings.

    Args:
        strings: Raw extracted strings.
        min_string_length: Minimum meaningful length.

    Returns:
        Potentially localizable strings.
    """
    return [s for s in strings if not _is_noise_string(s, min_string_length)]


def _is_mod_dll(dll_name: str, skip_dlls: set[str]) -> bool:
    """Check whether a DLL is the mod's own assembly rather than a known dependency.

    Args:
        dll_name: DLL filename.
        skip_dlls: DLL filenames to skip.

    Returns:
        True if it is the mod's own DLL.
    """
    return dll_name not in skip_dlls


def extract_mod_dll_strings(
    mod_path: Path,
    skip_dlls: set[str],
    min_string_length: int,
) -> list[str]:
    """Extract a flat list of localizable strings from the mod's own DLLs (known dependencies are skipped).

    Args:
        mod_path: Mod root directory.
        skip_dlls: DLL filenames to skip.
        min_string_length: Minimum meaningful length.

    Returns:
        Potentially localizable strings.
    """
    assemblies_dir = mod_path / "Assemblies"
    if not assemblies_dir.exists():
        return []

    all_strings = []

    for dll_file in assemblies_dir.glob("*.dll"):
        if not _is_mod_dll(dll_file.name, skip_dlls):
            continue

        print(f"  Extracting strings from {dll_file.name}...")
        raw_strings = extract_dll_strings(dll_file)
        filtered = filter_localizable_strings(raw_strings, min_string_length)
        all_strings.extend(filtered)
        print(f"    Found {len(raw_strings)} raw, {len(filtered)} after filtering")

    return all_strings


def extract_mod_dll_loc_strings(
    mod_path: Path,
    skip_dlls: set[str],
) -> dict[str, LocString]:
    """Extract `ldstr`-pair localization strings from the mod's DLLs, in the same shape as the CSV pipeline.

    Args:
        mod_path: Mod root directory.
        skip_dlls: DLL filenames to skip.

    Returns:
        `{key: LocString}`.
    """
    assemblies_dir = mod_path / "Assemblies"
    if not assemblies_dir.exists():
        return {}

    all_strings: dict[str, LocString] = {}

    for dll_file in assemblies_dir.glob("*.dll"):
        if not _is_mod_dll(dll_file.name, skip_dlls):
            continue

        print(f"  Extracting loc pairs from {dll_file.name}...")
        loc_strings = extract_dll_loc_strings(dll_file, source_file_label=dll_file.name)
        all_strings.update(loc_strings)
        print(f"    Found {len(loc_strings)} localization key-value pairs")

    return all_strings


def extract_mod_dll_orphan_strings(
    mod_path: Path,
    skip_dlls: set[str],
    paired_strings: dict[str, LocString],
    min_string_length: int = 4,
) -> dict[str, LocString]:
    """Extract CJK strings from the mod's DLLs that `extract_mod_dll_loc_strings` did not pair (see `extract_dll_orphan_strings`).

    Args:
        mod_path: Mod root directory.
        skip_dlls: DLL filenames to skip.
        paired_strings: Strings from the paired pass, whose values are excluded.
        min_string_length: Minimum string length to consider.

    Returns:
        `{synthetic key: LocString}`.
    """
    assemblies_dir = mod_path / "Assemblies"
    if not assemblies_dir.exists():
        return {}

    paired_values: set[str] = set()
    for loc_str in paired_strings.values():
        for val in loc_str.translations.values():
            if val:
                paired_values.add(val)

    all_strings: dict[str, LocString] = {}

    for dll_file in assemblies_dir.glob("*.dll"):
        if not _is_mod_dll(dll_file.name, skip_dlls):
            continue

        orphans = extract_dll_orphan_strings(
            dll_file,
            paired_values,
            source_file_label=dll_file.name,
            min_string_length=min_string_length,
        )
        all_strings.update(orphans)
        if orphans:
            print(f"    Found {len(orphans)} orphan CJK strings in {dll_file.name}")

    return all_strings
