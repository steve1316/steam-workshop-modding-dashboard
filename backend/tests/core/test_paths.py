"""Path helpers keep user-supplied names inside their base directory."""

from pathlib import Path

import pytest

from backend.core.paths import safe_child


def test_plain_names_resolve_under_the_base(tmp_path: Path):
    assert safe_child(tmp_path, "20261101_120000") == tmp_path / "20261101_120000"
    assert safe_child(tmp_path, "LangDataDB.csv") == tmp_path / "LangDataDB.csv"


@pytest.mark.parametrize("name", ["", ".", "..", "../x", "..\\x", "a/b", "a\\b", "C:x", "C:\\x"])
def test_names_that_could_escape_are_rejected(tmp_path: Path, name: str):
    with pytest.raises(ValueError):
        safe_child(tmp_path, name)
