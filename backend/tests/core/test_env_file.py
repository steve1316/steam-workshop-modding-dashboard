"""Settings saved to .env read back exactly as they were entered."""

from pathlib import Path

import pytest
from dotenv import dotenv_values

from backend.core import env_file

TRICKY_VALUES = [
    "8008",
    r"C:\Program Files (x86)\Steam\steamapps",
    "sk-abc #not-a-comment",
    "  padded  ",
    "it's",
    'say "hi"',
    "line one\nSWMT_INJECTED=1",
    "${HOME}",
    "",
]


@pytest.fixture
def env_path(tmp_path: Path, monkeypatch):
    """Point the .env writer at a temp file.

    Args:
        tmp_path: The pytest temp dir.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The temp .env path.
    """
    path = tmp_path / ".env"
    monkeypatch.setattr(env_file, "ENV_PATH", path)
    monkeypatch.setenv("SWMT_TEST_VALUE", "")
    monkeypatch.setenv("SWMT_API_PORT", "")
    return path


@pytest.mark.parametrize("value", TRICKY_VALUES)
def test_values_round_trip_through_dotenv(env_path: Path, value: str):
    env_file.update_env_file({"SWMT_TEST_VALUE": value})
    assert dotenv_values(env_path, interpolate=False) == {"SWMT_TEST_VALUE": value}


def test_existing_lines_and_comments_are_kept(env_path: Path):
    env_path.write_text("# Ports\nSWMT_API_PORT=8008\nSWMT_TEST_VALUE=old\n", encoding="utf-8")
    env_file.update_env_file({"SWMT_TEST_VALUE": "new value"})
    assert env_path.read_text(encoding="utf-8").splitlines()[:2] == ["# Ports", "SWMT_API_PORT=8008"]
    assert dotenv_values(env_path, interpolate=False) == {"SWMT_API_PORT": "8008", "SWMT_TEST_VALUE": "new value"}


def test_plain_values_stay_unquoted_for_the_vite_port_reader(env_path: Path):
    env_file.update_env_file({"SWMT_API_PORT": "8010"})
    assert env_path.read_text(encoding="utf-8").strip() == "SWMT_API_PORT=8010"
