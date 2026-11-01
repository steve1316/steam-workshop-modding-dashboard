"""Write settings back to the backend `.env` file without losing its comments or ordering."""

import os
from pathlib import Path

from backend.core.json_store import write_text_atomic

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
"""Path to the backend `.env` configuration file."""


def _format_env_value(value: str) -> str:
    """Quote a .env value only when python-dotenv would otherwise misread it.

    Args:
        value: Raw setting value.

    Returns:
        Value as written after `KEY=`.
    """
    # Plain values stay unquoted because vite.config.ts reads SWMT_API_PORT with a bare regex.
    if value == value.strip() and not any(c in value for c in "#$\n\r") and not value.startswith(("'", '"')):
        return value
    # Single quotes turn off ${VAR} expansion, and dotenv only unescapes \\ and \' inside them.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def update_env_file(updates: dict[str, str]) -> None:
    """Write SWMT_* values to the .env file and `os.environ`, replacing keys in place to keep comments and ordering.

    Args:
        updates: Env-var name (e.g. `SWMT_BATCH_SIZE`) to new value.
    """
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)

    found_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0]
            if key in updates:
                new_lines.append(f"{key}={_format_env_value(updates[key])}\n")
                found_keys.add(key)
                continue
        new_lines.append(line if line.endswith("\n") else line + "\n")

    for key, value in updates.items():
        if key not in found_keys:
            new_lines.append(f"{key}={_format_env_value(value)}\n")

    write_text_atomic(ENV_PATH, "".join(new_lines))

    # Avoids needing a restart for config reads.
    for key, value in updates.items():
        os.environ[key] = value
