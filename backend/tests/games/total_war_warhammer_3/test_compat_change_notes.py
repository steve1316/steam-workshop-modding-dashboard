"""Tests for the subprocess bridge to totalwar-modding's change note CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.core.settings import settings
from backend.games.total_war_warhammer_3.workshop import compat_change_notes as ccn


@pytest.fixture
def helper_dir(monkeypatch, tmp_path: Path) -> Path:
    """Point the helper_scripts setting at an existing temp folder."""
    monkeypatch.setattr(settings.tw3, "helper_path", str(tmp_path))
    return tmp_path


def _fake_run(monkeypatch, *, stdout: str = "", stderr: str = "", returncode: int = 0, calls: list | None = None) -> None:
    """Replace `subprocess.run` with a stub that returns a fixed result and records each call."""

    def fake(cmd, **kwargs):
        if calls is not None:
            calls.append({"cmd": cmd, **kwargs})
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(ccn.subprocess, "run", fake)


def test_preview_runs_the_cli_from_helper_scripts(helper_dir, monkeypatch):
    calls: list = []
    _fake_run(monkeypatch, stdout='{"1": {"note": "n", "pack_sha": "s", "pending": true}, "2": null}\n', calls=calls)

    assert ccn.preview(["1", "2"]) == {"1": {"note": "n", "pack_sha": "s", "pending": True}, "2": None}
    assert calls[0]["cmd"][1:] == ["-m", "publish.change_notes", "preview", "1", "2"]
    assert calls[0]["cwd"] == str(helper_dir)


def test_preview_parses_the_last_line_when_imports_print_first(helper_dir, monkeypatch):
    _fake_run(monkeypatch, stdout='loading tables...\n{"1": null}\n\n')

    assert ccn.preview(["1"]) == {"1": None}


def test_preview_maps_ids_missing_from_the_output_to_none(helper_dir, monkeypatch):
    _fake_run(monkeypatch, stdout="{}\n")

    assert ccn.preview(["1"]) == {"1": None}


def test_preview_with_no_ids_skips_the_cli(helper_dir, monkeypatch):
    calls: list = []
    _fake_run(monkeypatch, calls=calls)

    assert ccn.preview([]) == {}
    assert calls == []


def test_preview_timeout_grows_with_the_number_of_ids(helper_dir, monkeypatch):
    calls: list = []
    _fake_run(monkeypatch, stdout='{"1": null}\n', calls=calls)
    ccn.preview(["1"])

    calls.clear()
    _fake_run(monkeypatch, stdout='{"1": null, "2": null, "3": null}\n', calls=calls)
    ccn.preview(["1", "2", "3"])

    assert calls[0]["timeout"] == ccn.PREVIEW_TIMEOUT_SECONDS + ccn.PER_PACK_SECONDS * 3


def test_preview_raises_when_helper_path_unset(monkeypatch):
    monkeypatch.setattr(settings.tw3, "helper_path", "")

    with pytest.raises(ccn.ChangeNoteError, match="not configured"):
        ccn.preview(["1"])


def test_preview_raises_with_last_stderr_line_on_failure(helper_dir, monkeypatch):
    _fake_run(monkeypatch, returncode=1, stderr="Traceback (most recent call last):\nModuleNotFoundError: No module named 'publish.change_notes'\n")

    with pytest.raises(ccn.ChangeNoteError, match="No module named"):
        ccn.preview(["1"])


def test_preview_raises_on_non_json_output(helper_dir, monkeypatch):
    _fake_run(monkeypatch, stdout="oops\n")

    with pytest.raises(ccn.ChangeNoteError, match="JSON"):
        ccn.preview(["1"])


def test_preview_raises_on_timeout(helper_dir, monkeypatch):
    def fake(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(ccn.subprocess, "run", fake)

    with pytest.raises(ccn.ChangeNoteError, match="timed out"):
        ccn.preview(["1"])


def test_record_passes_the_note_through_a_utf8_file_and_removes_it(helper_dir, monkeypatch):
    seen: dict = {}

    def fake(cmd, **kwargs):
        path = cmd[cmd.index("--note-file") + 1]
        seen["path"] = path
        seen["note"] = Path(path).read_text(encoding="utf-8")
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(ccn.subprocess, "run", fake)

    ccn.record("1", "sha", '[u]Update[/u]\n\n• "Mod" A 苗英')

    assert seen["note"] == '[u]Update[/u]\n\n• "Mod" A 苗英'
    assert seen["cmd"][3:7] == ["record", "1", "--pack-sha", "sha"]
    assert not Path(seen["path"]).exists()


def test_record_raises_when_the_cli_fails(helper_dir, monkeypatch):
    _fake_run(monkeypatch, returncode=1, stderr="1 is not a generated Workshop item\n")

    with pytest.raises(ccn.ChangeNoteError, match="not a generated Workshop item"):
        ccn.record("1", "sha", "note")
