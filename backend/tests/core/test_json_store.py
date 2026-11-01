"""Atomic writes never leave a half-written file behind."""

import json
from pathlib import Path

import pytest

from backend.core import json_store
from backend.core.json_store import write_json, write_text_atomic


def test_write_json_round_trips_unicode(tmp_path: Path):
    path = tmp_path / "out.json"
    write_json(path, {"k": "테스트"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"k": "테스트"}
    assert "테스트" in path.read_text(encoding="utf-8")


def test_write_json_creates_missing_parents(tmp_path: Path):
    path = tmp_path / "a" / "b" / "out.json"
    write_json(path, [1, 2])
    assert json.loads(path.read_text(encoding="utf-8")) == [1, 2]


def test_failed_write_keeps_the_old_file_and_no_temp(tmp_path: Path, monkeypatch):
    path = tmp_path / "out.json"
    write_json(path, {"v": 1})

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(json_store.os, "replace", boom)
    with pytest.raises(OSError):
        write_json(path, {"v": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_unserializable_data_leaves_the_old_file(tmp_path: Path):
    path = tmp_path / "out.json"
    write_json(path, {"v": 1})
    with pytest.raises(TypeError):
        write_json(path, {"v": object()})
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 1}


def test_write_text_atomic_matches_write_text_newlines(tmp_path: Path):
    expected = tmp_path / "expected.tsv"
    expected.write_text("a\tb\nc\td\n", encoding="utf-8")
    path = tmp_path / "a.tsv"
    write_text_atomic(path, "a\tb\nc\td\n")
    assert path.read_bytes() == expected.read_bytes()


def test_write_text_atomic_can_keep_newlines_as_written(tmp_path: Path):
    path = tmp_path / "a.tsv"
    write_text_atomic(path, "a\tb\nc\td\n", newline="")
    assert path.read_bytes() == b"a\tb\nc\td\n"


def test_replace_retries_while_the_target_is_locked(tmp_path: Path, monkeypatch):
    path = tmp_path / "out.json"
    real_replace = json_store.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError("in use")
        real_replace(src, dst)

    monkeypatch.setattr(json_store.os, "replace", flaky)
    monkeypatch.setattr(json_store, "_REPLACE_DELAY_SECONDS", 0)
    write_json(path, {"v": 1})
    assert len(calls) == 3
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 1}
