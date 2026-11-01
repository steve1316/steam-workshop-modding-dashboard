"""Tests never read or write the real storage folder or .env file."""

from pathlib import Path

from backend.core import env_file
from backend.core.settings import settings

REAL_BACKEND = Path(__file__).resolve().parent.parent


def test_storage_and_env_point_at_temp(tmp_path: Path):
    assert settings.storage_path == tmp_path / "storage"
    assert settings.llamacpp_models_dir.is_relative_to(tmp_path)
    assert env_file.ENV_PATH == tmp_path / ".env"
    assert not settings.storage_path.is_relative_to(REAL_BACKEND)
