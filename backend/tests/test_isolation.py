"""Tests never read or write the real storage folder or .env file."""

from pathlib import Path

from backend import config
from backend.core import env_file

REAL_BACKEND = Path(__file__).resolve().parent.parent


def test_storage_and_env_point_at_temp(tmp_path: Path):
    assert config.STORAGE_PATH == tmp_path / "storage"
    assert config.LLAMACPP_MODELS_DIR.is_relative_to(tmp_path)
    assert env_file.ENV_PATH == tmp_path / ".env"
    assert not config.STORAGE_PATH.is_relative_to(REAL_BACKEND)
