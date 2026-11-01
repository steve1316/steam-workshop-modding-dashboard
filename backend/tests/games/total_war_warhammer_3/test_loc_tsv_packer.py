import subprocess
from pathlib import Path

import pytest
from backend.games.total_war_warhammer_3 import loc_tsv_packer
from backend.games.total_war_warhammer_3.loc_tsv_packer import (
    AmbiguousPackError,
    PackNotFoundError,
    RpfmFailedError,
    RpfmNotConfiguredError,
    build_translation_pack,
    resolve_rpfm_cli_path,
    resolve_target_pack,
)
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod


def test_resolve_target_pack_returns_single_pack(tmp_path: Path):
    (tmp_path / "MyMod.pack").write_bytes(b"x")
    assert resolve_target_pack(tmp_path) == tmp_path / "MyMod.pack"


def test_resolve_target_pack_raises_when_no_pack(tmp_path: Path):
    with pytest.raises(PackNotFoundError):
        resolve_target_pack(tmp_path)


def test_resolve_target_pack_raises_when_dir_missing(tmp_path: Path):
    with pytest.raises(PackNotFoundError):
        resolve_target_pack(tmp_path / "nope")


def test_resolve_target_pack_raises_when_multiple_packs(tmp_path: Path):
    (tmp_path / "a.pack").write_bytes(b"x")
    (tmp_path / "b.pack").write_bytes(b"x")
    with pytest.raises(AmbiguousPackError):
        resolve_target_pack(tmp_path)


def _mod(source_dir: Path) -> WH3TranslationMod:
    return WH3TranslationMod(
        workshop_id="3315737452",
        display_name="Test",
        parent_workshop_ids=("111",),
        local_source_dir=source_dir,
    )


def test_build_translation_pack_invokes_rpfm_delete_then_add(monkeypatch, tmp_path: Path):
    rpfm = tmp_path / "rpfm_cli.exe"
    rpfm.write_bytes(b"x")
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    pack = content_dir / "MyMod.pack"
    pack.write_bytes(b"x")
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        result = subprocess.CompletedProcess(cmd, 0)
        result.returncode = 0
        result.stderr = b""
        assert kwargs["cwd"] == str(rpfm.parent)
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)

    returned = build_translation_pack(_mod(source_dir), rpfm_cli_path=rpfm, workshop_content_dir=content_dir)

    assert returned == pack
    assert len(calls) == 2
    assert calls[0][:3] == [str(rpfm), "--game", "warhammer_3"]
    assert "delete" in calls[0] and "--folder-path" in calls[0] and "text" in calls[0]
    assert "--pack-path" in calls[0] and str(pack) in calls[0]
    assert "add" in calls[1] and "--tsv-to-binary" in calls[1]
    assert f"{source_dir};" in calls[1]
    schema = str(rpfm.parent / "schemas" / "schema_wh3.ron")
    assert schema in calls[1]


def test_build_translation_pack_raises_on_rpfm_nonzero(monkeypatch, tmp_path: Path):
    rpfm = tmp_path / "rpfm_cli.exe"
    rpfm.write_bytes(b"x")
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "MyMod.pack").write_bytes(b"x")

    def fake_run(cmd, **kwargs):
        result = subprocess.CompletedProcess(cmd, 2)
        result.returncode = 2
        result.stderr = b"boom"
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RpfmFailedError):
        build_translation_pack(_mod(tmp_path / "src"), rpfm_cli_path=rpfm, workshop_content_dir=content_dir)


def test_validate_loc_tsv_dir_passes_well_formed(tmp_path: Path):
    from backend.games.total_war_warhammer_3.loc_tsv_packer import validate_loc_tsv_dir

    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "ok.loc.tsv").write_text("key\ttext\ttooltip\n#Loc;1;text/ok.loc\t\t\nk1\tHello\ttrue\nk2\tLine1\\nLine2\tfalse\n", encoding="utf-8")
    validate_loc_tsv_dir(tmp_path)  # must not raise


def test_validate_loc_tsv_dir_rejects_embedded_newline(tmp_path: Path):
    from backend.games.total_war_warhammer_3.loc_tsv_packer import MalformedLocTsvError, validate_loc_tsv_dir

    text_dir = tmp_path / "text"
    text_dir.mkdir()
    # A real embedded newline splits one entry across two physical lines -> the continuation line has != 2 tabs.
    (text_dir / "bad.loc.tsv").write_text("key\ttext\ttooltip\n#Loc;1;text/bad.loc\t\t\nk1\tLine1\nLine2\ttrue\n", encoding="utf-8")
    with pytest.raises(MalformedLocTsvError):
        validate_loc_tsv_dir(tmp_path)


def test_build_translation_pack_real_rpfm_round_trips_multiline_keys(tmp_path: Path):
    """Real RPFM round-trip: a multi-line translation, escaped by the writeback, builds with all keys intact.

    Skips when rpfm_cli + schema are not configured on this machine.
    """
    from backend.games.total_war_warhammer_3.loc_extractor import escape_loc_text
    from backend.games.total_war_warhammer_3.loc_tsv_packer import resolve_rpfm_cli_path

    rpfm = resolve_rpfm_cli_path()
    if rpfm is None or not (rpfm.parent / "schemas" / "schema_wh3.ron").is_file():
        pytest.skip("rpfm_cli / schema_wh3.ron not configured")

    # Loose source: one plain key + one multi-line description, escaped exactly as the writeback would write it.
    source = tmp_path / "src"
    text_dir = source / "text"
    text_dir.mkdir(parents=True)
    desc = escape_loc_text("Para one.\nPara two with a tab\there.")
    (text_dir / "probe.loc.tsv").write_text(f"key\ttext\ttooltip\n#Loc;1;text/probe.loc\t\t\nk_title\tThe Title\tfalse\nk_desc\t{desc}\tfalse\n", encoding="utf-8")

    # Empty target pack in a workshop-content-style dir.
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    pack = content_dir / "probe.pack"
    subprocess.run([str(rpfm), "--game", "warhammer_3", "pack", "create", "--pack-path", str(pack)], capture_output=True, cwd=str(rpfm.parent))

    mod = WH3TranslationMod(workshop_id="1", display_name="t", parent_workshop_ids=("1",), local_source_dir=source)
    build_translation_pack(mod, rpfm_cli_path=rpfm, workshop_content_dir=content_dir)

    # Extract the built pack's loc keys and assert both real keys survived (no English-in-key corruption).
    out = tmp_path / "out"
    schema = str(rpfm.parent / "schemas" / "schema_wh3.ron")
    subprocess.run(
        [str(rpfm), "--game", "warhammer_3", "pack", "extract", "--pack-path", str(pack), "--tables-as-tsv", schema, "--folder-path", f"text;{out}"], capture_output=True, cwd=str(rpfm.parent)
    )
    extracted = list(out.rglob("probe.loc.tsv"))
    assert extracted, "no loc extracted from built pack"
    keys = {ln.split("\t")[0] for ln in extracted[0].read_text(encoding="utf-8").splitlines()[2:] if ln and "\t" in ln}
    assert "k_title" in keys
    assert "k_desc" in keys


def test_build_translation_pack_wraps_launch_failure_as_rpfm_failed(monkeypatch, tmp_path: Path):
    rpfm = tmp_path / "rpfm_cli.exe"
    rpfm.write_bytes(b"x")
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "MyMod.pack").write_bytes(b"x")

    def raise_oserror(cmd, **kwargs):
        raise FileNotFoundError("cannot launch")

    monkeypatch.setattr(subprocess, "run", raise_oserror)

    with pytest.raises(RpfmFailedError):
        build_translation_pack(_mod(tmp_path / "src"), rpfm_cli_path=rpfm, workshop_content_dir=content_dir)


def test_build_translation_pack_raises_when_rpfm_missing(tmp_path: Path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "MyMod.pack").write_bytes(b"x")
    with pytest.raises(RpfmNotConfiguredError):
        build_translation_pack(_mod(tmp_path / "src"), rpfm_cli_path=tmp_path / "missing.exe", workshop_content_dir=content_dir)


def test_resolve_rpfm_cli_path_prefers_config(monkeypatch, tmp_path: Path):
    rpfm = tmp_path / "rpfm_cli.exe"
    rpfm.write_bytes(b"x")
    monkeypatch.setattr(loc_tsv_packer.config, "TW3_RPFM_CLI_PATH", str(rpfm))
    assert resolve_rpfm_cli_path() == rpfm


def test_resolve_rpfm_cli_path_returns_none_when_unset(monkeypatch):
    monkeypatch.setattr(loc_tsv_packer.config, "TW3_RPFM_CLI_PATH", "")
    monkeypatch.setattr(loc_tsv_packer.config, "TW3_HELPER_PATH", "")
    assert resolve_rpfm_cli_path() is None
