from pathlib import Path

from backend.games.chrono_ark.csv_extractor import (
    _fix_oversized_row,
    classify_csv_file,
    extract_mod_strings,
    find_all_csv_files,
    get_untranslated_strings,
)
from backend.models.loc import LocString

CSV_HEADER = "Key,Type,Desc,Korean,English,Japanese,Chinese,Chinese-TW [zh-tw]\n"


def _write_csv(path: Path, rows: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(CSV_HEADER)
        for row in rows:
            f.write(row + "\n")


def test_find_all_csv_files_localization_dir(tmp_path):
    _write_csv(tmp_path / "Localization" / "LangDataDB.csv", ["Buff/B_1_Name,Text,,테스트,Test,,测试,測試"])
    files = find_all_csv_files(tmp_path)
    assert len(files) == 1
    assert files[0].name == "LangDataDB.csv"


def test_find_all_csv_files_detects_duplicates(tmp_path):
    _write_csv(tmp_path / "Localization" / "LangDataDB.csv", ["Buff/B_1_Name,Text,,테스트,Test,,测试,測試"])
    _write_csv(tmp_path / "Localization" / "LangDataDB - 副本.csv", ["Buff/B_1_Name,Text,,테스트,Test2,,测试,測試"])
    files = find_all_csv_files(tmp_path)
    assert len(files) == 2


def test_classify_canonical():
    loc_dir = Path("Localization")
    assert classify_csv_file(loc_dir / "LangDataDB.csv", loc_dir) == ("LangDataDB.csv", True)


def test_classify_variant_copy_suffix():
    loc_dir = Path("Localization")
    assert classify_csv_file(loc_dir / "LangDataDB - 副本.csv", loc_dir) == ("LangDataDB.csv", False)


def test_classify_variant_numbered():
    loc_dir = Path("Localization")
    assert classify_csv_file(loc_dir / "LangDataDB (1).csv", loc_dir) == ("LangDataDB.csv", False)


def test_classify_variant_fullwidth_parens():
    loc_dir = Path("Localization")
    canonical, is_canon = classify_csv_file(loc_dir / "LangDataDB\uff081\uff09.csv", loc_dir)
    assert canonical == "LangDataDB.csv"
    assert is_canon is False


def test_classify_variant_versioned():
    canonical, is_canon = classify_csv_file(Path("LangDataDB_v0.6.13.csv"), Path("."))
    assert canonical == "LangDataDB.csv"
    assert is_canon is False


def test_classify_backup_dir():
    canonical, is_canon = classify_csv_file(Path("langbackup/LangDataDB.csv"), Path("."))
    assert canonical == "LangDataDB.csv"
    assert is_canon is False


def test_classify_chinese_backup_dir():
    canonical, is_canon = classify_csv_file(Path("备份/LangDataDB.csv"), Path("."))
    assert canonical == "LangDataDB.csv"
    assert is_canon is False


def test_extract_mod_strings_deduplicates(tmp_path):
    _write_csv(
        tmp_path / "Localization" / "LangDataDB.csv",
        [
            "Buff/B_1_Name,Text,,테스트,Canonical,,测试,測試",
            "Buff/B_2_Name,Text,,테스트2,Test2,,测试2,測試2",
        ],
    )
    _write_csv(
        tmp_path / "Localization" / "LangDataDB - 副本.csv",
        [
            "Buff/B_1_Name,Text,,테스트,FromCopy,,测试,測試",
            "Buff/B_3_Name,Text,,테스트3,Test3,,测试3,測試3",
        ],
    )
    strings, variants = extract_mod_strings(tmp_path)
    # Canonical wins on key collision.
    assert strings["Buff/B_1_Name"].translations["English"] == "Canonical"
    # Unique keys from variant are included.
    assert "Buff/B_3_Name" in strings
    # Variants are reported.
    assert len(variants) == 1
    assert "副本" in variants[0]


def test_fix_oversized_row_merges_korean_with_commas():
    """Korean field with unquoted commas should be merged back together."""
    col_indices = {
        "Key": 0,
        "Type": 1,
        "Desc": 2,
        "Korean": 3,
        "English": 4,
        "Japanese": 5,
        "Chinese": 6,
        "Chinese-TW [zh-tw]": 7,
        "": 8,
    }
    # Simulate csv.reader splitting Korean field into 3 columns (+ trailing empty
    # from trailing comma in both header and data, matching real CSV format).
    row = [
        "Buff/B_Test",
        "Text",
        "",
        '"로직 아틀리에"와 공격을 받을 때마다',
        "받는 치명타 확률 10%",
        '받는 치명타 피해 25% 증가합니다."',
        "Increase critical hit chance by 10%",
        "日本語テスト",
        "中文测试",
        "",
        "",
    ]
    fixed = _fix_oversized_row(row, 9, col_indices)
    assert len(fixed) == 9
    assert "Increase critical hit" in fixed[col_indices["English"]]
    assert "치명타" in fixed[col_indices["Korean"]]
    assert "日本語" in fixed[col_indices["Japanese"]]
    assert "中文" in fixed[col_indices["Chinese"]]


def test_extract_mod_strings_keys_with_spaces(tmp_path):
    """Keys containing spaces (e.g. character names) must not be merged."""
    _write_csv(
        tmp_path / "Localization" / "LangDataDB.csv",
        [
            "Buff/B_1_Name,Text,,영시,Spiritual vision,,灵视,靈視",
            "Character/Suzakuin Momiji_name,Text,,스자쿠인 모미지,Suzakuin Momiji,,朱雀院红叶,朱雀院紅葉",
            "Character/Suzakuin Momiji_PassiveName,Text,,신안극수,God's eye,,神眼极手,神眼極手",
        ],
    )
    strings, _ = extract_mod_strings(tmp_path)
    # Each key should be a separate entry.
    assert "Buff/B_1_Name" in strings
    assert "Character/Suzakuin Momiji_name" in strings
    assert "Character/Suzakuin Momiji_PassiveName" in strings
    # Values must not leak between entries.
    assert strings["Buff/B_1_Name"].translations["Chinese"] == "灵视"
    assert strings["Buff/B_1_Name"].translations["English"] == "Spiritual vision"
    assert strings["Character/Suzakuin Momiji_name"].translations["Korean"] == "스자쿠인 모미지"


def test_extract_mod_strings_handles_unquoted_commas(tmp_path):
    """End-to-end: a CSV with unquoted commas in Korean parses correctly."""
    # Real Chrono Ark CSVs have a trailing comma on every line, producing an
    # extra empty column.  This matches the actual file format.
    csv_content = (
        "Key,Type,Desc,Korean,English,Japanese,Chinese,Chinese-TW [zh-tw],\n"
        'Buff/B_6_T_Description,Text,,""로직 아틀리에"와 그가 관련된 스킬의 공격을 받을 때마다,'
        "받는 치명타 확률 10% ,"
        '받는 치명타 피해 25% 증가합니다.",'
        "Increase critical hit chance by 10% and critical hit damage by 25%.,"
        "「ロジックアトリエ」やそれに関するスキルからの攻撃を受ける時,"
        "受到技能逻辑工作室及其衍生技能的攻击时,,\n"
    )
    loc_dir = tmp_path / "Localization"
    loc_dir.mkdir()
    csv_path = loc_dir / "LangDataDB.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    strings, _ = extract_mod_strings(tmp_path)
    entry = strings["Buff/B_6_T_Description"]
    assert "Increase critical hit" in entry.translations["English"]
    assert "치명타" in entry.translations["Korean"]
    assert "ロジック" in entry.translations["Japanese"]
    assert "逻辑工作室" in entry.translations["Chinese"]


def test_get_untranslated_strings_checks_the_target_language_column():
    strings = {
        "a": LocString(key="a", type="Text", desc="", translations={"Korean": "가", "English": "A"}),
        "b": LocString(key="b", type="Text", desc="", translations={"Korean": "나", "Japanese": "ナ"}),
    }

    assert set(get_untranslated_strings(strings, ["Korean"])) == {"b"}
    assert set(get_untranslated_strings(strings, ["Korean"], target_lang="Japanese")) == {"a"}
