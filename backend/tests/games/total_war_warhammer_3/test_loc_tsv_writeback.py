"""Tests for the WH3 `.loc.tsv` surgical writeback."""

from pathlib import Path

from backend.games.total_war_warhammer_3.loc_tsv_writeback import (
    apply_row_patches,
    read_loc_tsv_lines,
    remove_keys_from_loc_tsv,
    sync_translations_to_loc_tsv,
)
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod


def _write_loc_tsv(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="")


SAMPLE = "key\ttext\ttooltip\n#Loc;1;text/sample.loc\t\t\nkey_a\tOld A\ttrue\nkey_b\tOld B\tfalse\n"


def test_read_loc_tsv_lines_preserves_header_and_metadata(tmp_path: Path):
    p = tmp_path / "a.loc.tsv"
    _write_loc_tsv(p, SAMPLE)
    lines = read_loc_tsv_lines(p)
    assert lines[0].startswith("key\ttext\ttooltip")
    assert lines[1].startswith("#Loc;1;text/sample.loc")


def test_apply_row_patches_replaces_existing_text(tmp_path: Path):
    p = tmp_path / "a.loc.tsv"
    _write_loc_tsv(p, SAMPLE)
    apply_row_patches(p, {"key_a": "New A"})
    body = p.read_text(encoding="utf-8")
    assert "key_a\tNew A\ttrue" in body
    assert "key_b\tOld B\tfalse" in body  # untouched
    assert "Old A" not in body


def test_apply_row_patches_preserves_other_rows_verbatim(tmp_path: Path):
    p = tmp_path / "a.loc.tsv"
    _write_loc_tsv(p, SAMPLE)
    apply_row_patches(p, {"key_a": "New A"})
    lines = p.read_text(encoding="utf-8").splitlines()
    # Header + metadata + 2 data rows = 4 lines.
    assert len(lines) == 4
    assert lines[0] == "key\ttext\ttooltip"
    assert lines[1] == "#Loc;1;text/sample.loc\t\t"


def test_apply_row_patches_appends_new_keys(tmp_path: Path):
    p = tmp_path / "a.loc.tsv"
    _write_loc_tsv(p, SAMPLE)
    apply_row_patches(p, {"key_c": "Brand new"})
    body = p.read_text(encoding="utf-8")
    assert "key_c\tBrand new\ttrue" in body
    assert "key_a\tOld A\ttrue" in body  # original preserved


def test_apply_row_patches_handles_text_with_tabs_in_old_row(tmp_path: Path):
    """A pathological existing row with embedded literal `\\t` is not corrupted."""
    p = tmp_path / "a.loc.tsv"
    _write_loc_tsv(p, "key\ttext\ttooltip\n#Loc;1;text/x.loc\t\t\nweird\tone\\ttwo\\tthree\ttrue\n")
    apply_row_patches(p, {"weird": "fixed"})
    body = p.read_text(encoding="utf-8")
    # Row replaced; literal column count stays at 3 tab-separated columns.
    rows = [ln for ln in body.splitlines() if ln.startswith("weird\t")]
    assert rows == ["weird\tfixed\ttrue"]


def test_apply_row_patches_creates_file_when_missing(tmp_path: Path):
    p = tmp_path / "new.loc.tsv"
    assert not p.exists()
    apply_row_patches(p, {"key_a": "Hello"})
    body = p.read_text(encoding="utf-8")
    assert body.startswith("key\ttext\ttooltip\n")
    assert "#Loc;1;text/new.loc\t\t" in body
    assert "key_a\tHello\ttrue" in body


def test_sync_updates_existing_file_in_place(tmp_path: Path, monkeypatch):
    """Sync resolves source_filename -> existing prefixed user file and patches it."""
    local_dir = tmp_path / "translation_mod"
    text_dir = local_dir / "text"
    text_dir.mkdir(parents=True)
    user_file = text_dir / "@@my_units.loc.tsv"
    _write_loc_tsv(
        user_file,
        "key\ttext\ttooltip\n#Loc;1;text/@@my_units.loc\t\t\nkey_a\tOld A\ttrue\n",
    )

    mod = WH3TranslationMod(
        workshop_id="abc",
        display_name="t",
        parent_workshop_ids=("p",),
        local_source_dir=local_dir,
    )

    # Drift rows pointing at the normalized filename
    drift_rows = [
        {"source_filename": "my_units.loc.tsv", "key": "key_a", "translation_text": "New A"},
        {"source_filename": "my_units.loc.tsv", "key": "key_new", "translation_text": "Brand new"},
    ]
    result = sync_translations_to_loc_tsv(mod, drift_rows)

    body = user_file.read_text(encoding="utf-8")
    assert "key_a\tNew A\ttrue" in body
    assert "key_new\tBrand new\ttrue" in body
    assert result == {str(user_file): 2}


def test_sync_creates_new_file_with_prefix_when_no_existing_match(tmp_path: Path):
    local_dir = tmp_path / "translation_mod"
    (local_dir / "text").mkdir(parents=True)

    mod = WH3TranslationMod(
        workshop_id="abc",
        display_name="t",
        parent_workshop_ids=("p",),
        local_source_dir=local_dir,
        prefix="!!!",
    )
    drift_rows = [
        {"source_filename": "new_unit.loc.tsv", "key": "k1", "translation_text": "Hello"},
    ]
    result = sync_translations_to_loc_tsv(mod, drift_rows)

    expected = local_dir / "text" / "!!!new_unit.loc.tsv"
    assert expected.exists()
    assert "k1\tHello\ttrue" in expected.read_text(encoding="utf-8")
    assert result == {str(expected): 1}


def test_sync_skips_rows_with_null_translation_text(tmp_path: Path):
    local_dir = tmp_path / "translation_mod"
    (local_dir / "text").mkdir(parents=True)
    mod = WH3TranslationMod(
        workshop_id="abc",
        display_name="t",
        parent_workshop_ids=("p",),
        local_source_dir=local_dir,
    )
    drift_rows = [
        {"source_filename": "a.loc.tsv", "key": "k1", "translation_text": None},
        {"source_filename": "a.loc.tsv", "key": "k2", "translation_text": "x"},
    ]
    result = sync_translations_to_loc_tsv(mod, drift_rows)
    # Only one file touched, with one patch.
    assert sum(result.values()) == 1


def test_remove_keys_from_loc_tsv_drops_rows_and_keeps_header(tmp_path: Path):
    source = tmp_path / "translation_mod"
    loc = source / "text" / "sample.loc.tsv"
    _write_loc_tsv(loc, SAMPLE)  # contains key_a and key_b
    mod = WH3TranslationMod(workshop_id="abc", display_name="t", parent_workshop_ids=("p",), local_source_dir=source)

    result = remove_keys_from_loc_tsv(mod, {"sample.loc.tsv": {"key_a"}})

    assert result[str(loc)] == 1
    lines = loc.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "key\ttext\ttooltip"
    assert lines[1] == "#Loc;1;text/sample.loc\t\t"
    assert len(lines) == 3  # header + metadata + key_b
    assert "key_a" not in loc.read_text(encoding="utf-8")
    assert "key_b\tOld B\tfalse" in loc.read_text(encoding="utf-8")


def test_remove_keys_from_loc_tsv_noop_when_key_absent(tmp_path: Path):
    source = tmp_path / "translation_mod"
    loc = source / "text" / "sample.loc.tsv"
    _write_loc_tsv(loc, SAMPLE)
    mod = WH3TranslationMod(workshop_id="abc", display_name="t", parent_workshop_ids=("p",), local_source_dir=source)

    result = remove_keys_from_loc_tsv(mod, {"sample.loc.tsv": {"nonexistent"}})

    assert result == {}
    assert "key_a\tOld A\ttrue" in loc.read_text(encoding="utf-8")
