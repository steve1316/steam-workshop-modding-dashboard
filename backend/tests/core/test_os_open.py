"""Tests for the OS open helpers."""

from pathlib import Path

import pytest

from backend.core import os_open


@pytest.fixture
def popen_calls(monkeypatch) -> list[list[str]]:
    """Record `subprocess.Popen` args instead of launching anything.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The recorded argument lists.
    """
    calls: list[list[str]] = []
    monkeypatch.setattr(os_open.subprocess, "Popen", lambda args: calls.append(list(args)))
    return calls


def test_open_path_uses_startfile_on_windows(monkeypatch, popen_calls):
    opened: list[Path] = []
    monkeypatch.setattr(os_open.sys, "platform", "win32")
    monkeypatch.setattr(os_open.os, "startfile", opened.append, raising=False)
    os_open.open_path(Path("C:/mods/123"))
    assert opened == [Path("C:/mods/123")]
    assert popen_calls == []


@pytest.mark.parametrize(("platform", "command"), [("darwin", "open"), ("linux", "xdg-open")])
def test_open_path_shells_out_elsewhere(monkeypatch, popen_calls, platform: str, command: str):
    monkeypatch.setattr(os_open.sys, "platform", platform)
    os_open.open_path(Path("/mods/123"))
    assert popen_calls == [[command, str(Path("/mods/123"))]]


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", ["explorer", "/select,", str(Path("/game/LangDataDB.csv"))]),
        ("darwin", ["open", "-R", str(Path("/game/LangDataDB.csv"))]),
        ("linux", ["xdg-open", str(Path("/game"))]),
    ],
)
def test_reveal_path_selects_the_file_where_the_os_can(monkeypatch, popen_calls, platform: str, expected: list[str]):
    monkeypatch.setattr(os_open.sys, "platform", platform)
    os_open.reveal_path(Path("/game/LangDataDB.csv"))
    assert popen_calls == [expected]
