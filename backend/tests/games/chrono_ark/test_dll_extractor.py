import hashlib
from pathlib import Path
from unittest.mock import patch

from backend.games.chrono_ark.dll_extractor import (
    _is_loc_key,
    _is_mod_dll,
    _is_noise_string,
    extract_dll_loc_strings,
    extract_dll_orphan_strings,
    extract_dll_strings,
    extract_mod_dll_loc_strings,
    extract_mod_dll_orphan_strings,
    extract_mod_dll_strings,
    filter_localizable_strings,
)
from backend.models.loc import LocString

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Helpers


def _fake_us_map(strings: list[str]) -> dict[int, str]:
    """Build a fake #US heap map from a list of strings."""
    return {i: s for i, s in enumerate(strings)}


def _sha8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# _is_noise_string


def test_noise_too_short():
    assert _is_noise_string("hi", 4) is True


def test_noise_file_path():
    assert _is_noise_string("Assets/Amethyst/icon.png", 4) is True


def test_noise_backslash_path():
    assert _is_noise_string("Assets\\Amethyst\\icon.png", 4) is True


def test_noise_url():
    assert _is_noise_string("https://example.com", 4) is True


def test_noise_dotnet_namespace():
    assert _is_noise_string("System.Collections.Generic", 4) is True


def test_noise_pascal_case_identifier():
    assert _is_noise_string("ButtonElement", 4) is True


def test_noise_version_string():
    assert _is_noise_string("1.2.3", 4) is True


def test_noise_single_char_repeated():
    assert _is_noise_string("aaaa", 4) is True


def test_noise_format_string():
    assert _is_noise_string("{0}", 4) is True


def test_not_noise_cjk_text():
    assert _is_noise_string("获得一个专属消耗品。", 4) is False


def test_not_noise_english_sentence():
    assert _is_noise_string("Gain an exclusive consumable.", 4) is False


def test_noise_http_url():
    assert _is_noise_string("http://example.com/page", 4) is True


def test_not_noise_mixed_case_with_spaces():
    """Multi-word strings with spaces are not PascalCase identifiers."""
    assert _is_noise_string("Some description text here", 4) is False


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# _is_loc_key


def test_loc_key_valid():
    assert _is_loc_key("Buff/B_Armor_P_1_Name") is True


def test_loc_key_valid_dots():
    assert _is_loc_key("Text.Battle.Idle") is True


def test_loc_key_valid_hyphens():
    assert _is_loc_key("some-key-name") is True


def test_loc_key_empty():
    assert _is_loc_key("") is False


def test_loc_key_with_spaces():
    assert _is_loc_key("has space") is False


def test_loc_key_cjk():
    assert _is_loc_key("紫宝石") is False


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# _is_mod_dll


def test_is_mod_dll_own():
    assert _is_mod_dll("mymod.dll", {"0Harmony.dll"}) is True


def test_is_mod_dll_skip():
    assert _is_mod_dll("0Harmony.dll", {"0Harmony.dll"}) is False


def test_is_mod_dll_empty_skip():
    assert _is_mod_dll("anything.dll", set()) is True


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# filter_localizable_strings


def test_filter_localizable_strings():
    raw = [
        "hi",  # too short
        "System.Collections.Generic",  # namespace
        "获得一个专属消耗品。",  # real text
        "https://example.com",  # URL
        "Gain an exclusive consumable.",  # real text
    ]
    result = filter_localizable_strings(raw, min_string_length=4)
    assert "获得一个专属消耗品。" in result
    assert "Gain an exclusive consumable." in result
    assert len(result) == 2


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_dll_orphan_strings


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_extracts_cjk_strings(mock_load, mock_heap):
    """Orphan CJK strings are extracted with hash-based keys."""
    mock_load.return_value = object()  # non-None means success
    mock_heap.return_value = _fake_us_map(
        [
            "获得一个专属消耗品。",
            "ASCII only string here",
            "每回合第一张进入手中的非露西技能",
        ]
    )

    result = extract_dll_orphan_strings(
        Path("Assemblies/zibaoshi.dll"),
        paired_values=set(),
        source_file_label="zibaoshi.dll",
    )

    assert len(result) == 2
    key1 = f"DLL/zibaoshi/{_sha8('获得一个专属消耗品。')}"
    key2 = f"DLL/zibaoshi/{_sha8('每回合第一张进入手中的非露西技能')}"
    assert key1 in result
    assert key2 in result
    assert result[key1].translations["Chinese"] == "获得一个专属消耗品。"
    assert result[key1].source_file == "zibaoshi.dll"


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_excludes_paired_values(mock_load, mock_heap):
    """CJK strings already captured as paired key-value are excluded."""
    mock_load.return_value = object()
    mock_heap.return_value = _fake_us_map(
        [
            "已配对的中文字符串",
            "未配对的中文字符串",
        ]
    )

    result = extract_dll_orphan_strings(
        Path("Assemblies/test.dll"),
        paired_values={"已配对的中文字符串"},
    )

    assert len(result) == 1
    key = f"DLL/test/{_sha8('未配对的中文字符串')}"
    assert key in result


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_filters_noise(mock_load, mock_heap):
    """Noise strings (too short, paths, etc.) are filtered out."""
    mock_load.return_value = object()
    mock_heap.return_value = _fake_us_map(
        [
            "短",  # too short (1 char < 4)
            "Assets/紫宝石/icon.png",  # file path with CJK
            "获得一个专属消耗品。",  # real text
        ]
    )

    result = extract_dll_orphan_strings(
        Path("Assemblies/test.dll"),
        paired_values=set(),
    )

    assert len(result) == 1


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_deterministic_keys(mock_load, mock_heap):
    """Same string always produces the same key."""
    text = "每回合第一张进入手中的非露西技能"
    mock_load.return_value = object()
    mock_heap.return_value = _fake_us_map([text])

    result1 = extract_dll_orphan_strings(Path("Assemblies/mod.dll"), set())
    result2 = extract_dll_orphan_strings(Path("Assemblies/mod.dll"), set())

    assert list(result1.keys()) == list(result2.keys())


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_marked_untranslatable(mock_load, mock_heap):
    """Orphan strings have a non-empty untranslatable_reason."""
    mock_load.return_value = object()
    mock_heap.return_value = _fake_us_map(["获得一个专属消耗品。"])

    result = extract_dll_orphan_strings(Path("Assemblies/mod.dll"), set())

    loc_str = list(result.values())[0]
    assert loc_str.untranslatable_reason
    assert "DLL" in loc_str.untranslatable_reason


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_orphan_empty_on_pe_failure(mock_load, mock_heap):
    """Returns empty dict when the DLL cannot be parsed."""
    mock_load.return_value = None

    result = extract_dll_orphan_strings(Path("bad.dll"), set())

    assert result == {}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_mod_dll_orphan_strings


@patch("backend.games.chrono_ark.dll_extractor.extract_dll_orphan_strings")
def test_mod_orphan_skips_dependency_dlls(mock_extract, tmp_path):
    """Known dependency DLLs (e.g. 0Harmony.dll) are skipped."""
    asm_dir = tmp_path / "Assemblies"
    asm_dir.mkdir()
    (asm_dir / "0Harmony.dll").write_bytes(b"")
    (asm_dir / "mymod.dll").write_bytes(b"")

    mock_extract.return_value = {}

    extract_mod_dll_orphan_strings(
        tmp_path,
        skip_dlls={"0Harmony.dll"},
        paired_strings={},
    )

    # Only mymod.dll should be processed.
    assert mock_extract.call_count == 1
    assert mock_extract.call_args[0][0].name == "mymod.dll"


@patch("backend.games.chrono_ark.dll_extractor.extract_dll_orphan_strings")
def test_mod_orphan_passes_paired_values(mock_extract, tmp_path):
    """Paired string values are forwarded to exclude from orphans."""
    asm_dir = tmp_path / "Assemblies"
    asm_dir.mkdir()
    (asm_dir / "mod.dll").write_bytes(b"")

    paired = {
        "SomeKey": LocString(
            key="SomeKey",
            type="Text",
            desc="",
            translations={"Chinese": "已配对的中文"},
        ),
    }
    mock_extract.return_value = {}

    extract_mod_dll_orphan_strings(
        tmp_path,
        skip_dlls=set(),
        paired_strings=paired,
    )

    passed_paired_values = mock_extract.call_args[0][1]
    assert "已配对的中文" in passed_paired_values


def test_mod_orphan_no_assemblies_dir(tmp_path):
    """Returns empty dict when there is no Assemblies directory."""
    result = extract_mod_dll_orphan_strings(tmp_path, set(), {})
    assert result == {}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_dll_strings


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_extract_dll_strings_returns_all(mock_load, mock_heap):
    """Returns flat list of all user strings from the heap."""
    mock_load.return_value = object()
    mock_heap.return_value = _fake_us_map(["hello", "world", "测试"])

    result = extract_dll_strings(Path("test.dll"))

    assert set(result) == {"hello", "world", "测试"}


@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_extract_dll_strings_pe_failure(mock_load):
    """Returns empty list when DLL cannot be parsed."""
    mock_load.return_value = None

    result = extract_dll_strings(Path("bad.dll"))

    assert result == []


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_dll_loc_strings


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_pe_failure(mock_load, mock_heap):
    """Returns empty dict when DLL cannot be parsed."""
    mock_load.return_value = None

    result = extract_dll_loc_strings(Path("bad.dll"))

    assert result == {}


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_empty_heap(mock_load, mock_heap):
    """Returns empty dict when the US heap has no strings."""
    mock_load.return_value = object()
    mock_heap.return_value = {}

    result = extract_dll_loc_strings(Path("empty.dll"))

    assert result == {}


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_finds_key_value_pair(mock_load, mock_heap, tmp_path):
    """Finds a key-value pair from consecutive ldstr instructions."""
    # Build a fake DLL with two consecutive ldstr instructions.
    # ldstr opcode = 0x72, followed by 4-byte LE token (0x70xxxxxx for #US).
    import struct

    us_map = {0x01: "MyKey", 0x02: "中文翻译文本"}
    mock_load.return_value = object()
    mock_heap.return_value = us_map

    # Two back-to-back ldstr instructions (5 bytes each).
    token1 = 0x70000001  # US offset 0x01
    token2 = 0x70000002  # US offset 0x02
    dll_bytes = b"\x00" * 10  # padding
    dll_bytes += bytes([0x72]) + struct.pack("<I", token1)
    dll_bytes += bytes([0x72]) + struct.pack("<I", token2)
    dll_bytes += b"\x00" * 10  # padding

    dll_file = tmp_path / "mod.dll"
    dll_file.write_bytes(dll_bytes)

    result = extract_dll_loc_strings(dll_file, source_file_label="mod.dll")

    assert "MyKey" in result
    assert result["MyKey"].translations["Chinese"] == "中文翻译文本"
    assert result["MyKey"].source_file == "mod.dll"


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_reversed_order(mock_load, mock_heap, tmp_path):
    """Handles CJK-then-key order (value before key)."""
    import struct

    us_map = {0x01: "中文值", 0x02: "TheKey"}
    mock_load.return_value = object()
    mock_heap.return_value = us_map

    token1 = 0x70000001
    token2 = 0x70000002
    dll_bytes = b"\x00" * 10
    dll_bytes += bytes([0x72]) + struct.pack("<I", token1)
    dll_bytes += bytes([0x72]) + struct.pack("<I", token2)
    dll_bytes += b"\x00" * 10

    dll_file = tmp_path / "mod.dll"
    dll_file.write_bytes(dll_bytes)

    result = extract_dll_loc_strings(dll_file)

    assert "TheKey" in result
    assert result["TheKey"].translations["Chinese"] == "中文值"


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_skips_asset_keys(mock_load, mock_heap, tmp_path):
    """Keys ending with asset extensions are skipped."""
    import struct

    us_map = {0x01: "Assets/icon.png", 0x02: "中文文本"}
    mock_load.return_value = object()
    mock_heap.return_value = us_map

    token1 = 0x70000001
    token2 = 0x70000002
    dll_bytes = b"\x00" * 10
    dll_bytes += bytes([0x72]) + struct.pack("<I", token1)
    dll_bytes += bytes([0x72]) + struct.pack("<I", token2)
    dll_bytes += b"\x00" * 10

    dll_file = tmp_path / "mod.dll"
    dll_file.write_bytes(dll_bytes)

    result = extract_dll_loc_strings(dll_file)

    assert len(result) == 0


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_skips_wide_gap(mock_load, mock_heap, tmp_path):
    """Pairs with more than MAX_GAP bytes between them are skipped."""
    import struct

    us_map = {0x01: "MyKey", 0x02: "中文翻译"}
    mock_load.return_value = object()
    mock_heap.return_value = us_map

    token1 = 0x70000001
    token2 = 0x70000002
    # 20-byte gap between instructions (exceeds MAX_GAP=10).
    dll_bytes = b"\x00" * 10
    dll_bytes += bytes([0x72]) + struct.pack("<I", token1)
    dll_bytes += b"\x00" * 20  # large gap
    dll_bytes += bytes([0x72]) + struct.pack("<I", token2)
    dll_bytes += b"\x00" * 10

    dll_file = tmp_path / "mod.dll"
    dll_file.write_bytes(dll_bytes)

    result = extract_dll_loc_strings(dll_file)

    assert len(result) == 0


@patch("backend.games.chrono_ark.dll_extractor._build_us_heap_map")
@patch("backend.games.chrono_ark.dll_extractor._load_dotnet_pe")
def test_loc_strings_no_untranslatable_flag(mock_load, mock_heap, tmp_path):
    """Paired loc strings do NOT have untranslatable_reason set."""
    import struct

    us_map = {0x01: "MyKey", 0x02: "中文翻译文本"}
    mock_load.return_value = object()
    mock_heap.return_value = us_map

    token1 = 0x70000001
    token2 = 0x70000002
    dll_bytes = b"\x00" * 10
    dll_bytes += bytes([0x72]) + struct.pack("<I", token1)
    dll_bytes += bytes([0x72]) + struct.pack("<I", token2)
    dll_bytes += b"\x00" * 10

    dll_file = tmp_path / "mod.dll"
    dll_file.write_bytes(dll_bytes)

    result = extract_dll_loc_strings(dll_file)

    assert result["MyKey"].untranslatable_reason == ""


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_mod_dll_strings


@patch("backend.games.chrono_ark.dll_extractor.extract_dll_strings")
def test_mod_dll_strings_skips_deps(mock_extract, tmp_path):
    """Known dependency DLLs are skipped in flat extraction."""
    asm_dir = tmp_path / "Assemblies"
    asm_dir.mkdir()
    (asm_dir / "Mono.Cecil.dll").write_bytes(b"")
    (asm_dir / "mymod.dll").write_bytes(b"")

    mock_extract.return_value = ["some string"]

    extract_mod_dll_strings(tmp_path, skip_dlls={"Mono.Cecil.dll"}, min_string_length=4)

    assert mock_extract.call_count == 1
    assert mock_extract.call_args[0][0].name == "mymod.dll"


def test_mod_dll_strings_no_assemblies(tmp_path):
    """Returns empty list when no Assemblies directory exists."""
    result = extract_mod_dll_strings(tmp_path, set(), 4)
    assert result == []


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# extract_mod_dll_loc_strings


@patch("backend.games.chrono_ark.dll_extractor.extract_dll_loc_strings")
def test_mod_dll_loc_strings_skips_deps(mock_extract, tmp_path):
    """Known dependency DLLs are skipped in paired extraction."""
    asm_dir = tmp_path / "Assemblies"
    asm_dir.mkdir()
    (asm_dir / "0Harmony.dll").write_bytes(b"")
    (asm_dir / "mymod.dll").write_bytes(b"")

    mock_extract.return_value = {}

    extract_mod_dll_loc_strings(tmp_path, skip_dlls={"0Harmony.dll"})

    assert mock_extract.call_count == 1
    assert mock_extract.call_args[0][0].name == "mymod.dll"


def test_mod_dll_loc_strings_no_assemblies(tmp_path):
    """Returns empty dict when no Assemblies directory exists."""
    result = extract_mod_dll_loc_strings(tmp_path, set())
    assert result == {}


@patch("backend.games.chrono_ark.dll_extractor.extract_dll_loc_strings")
def test_mod_dll_loc_strings_merges_multiple_dlls(mock_extract, tmp_path):
    """Results from multiple mod DLLs are merged."""
    asm_dir = tmp_path / "Assemblies"
    asm_dir.mkdir()
    (asm_dir / "a.dll").write_bytes(b"")
    (asm_dir / "b.dll").write_bytes(b"")

    call_count = [0]

    def side_effect(dll_path, source_file_label=""):
        call_count[0] += 1
        key = f"Key{call_count[0]}"
        return {key: LocString(key=key, type="Text", desc="", translations={"Chinese": f"值{call_count[0]}"})}

    mock_extract.side_effect = side_effect

    result = extract_mod_dll_loc_strings(tmp_path, skip_dlls=set())

    assert len(result) == 2
    assert "Key1" in result
    assert "Key2" in result
