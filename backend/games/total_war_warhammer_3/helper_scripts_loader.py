"""Live importlib-based loader for the helper_scripts registry constants.

Reads `SUPPORTED_MODS` from `data/supported_mods.py` and `SUPPORTED_EFFECTS` from `data/dynamic_rors_effects.py`.
The registry files import other helper_scripts packages, so `sys.path` is prepended with that directory during the import.
Errors are typed for the routes.
"""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any, Iterator


_TW3_APPID_FOLDER = "1142710"

# Registry files, relative to the helper_scripts directory.
SUPPORTED_MODS_FILE = "data/supported_mods.py"
SUPPORTED_EFFECTS_FILE = "data/dynamic_rors_effects.py"


def _derive_workshop_id(path: str | None) -> str | None:
    """Extract the Workshop item id from a TW3 `.pack` file path.

    The Steam convention is `<...>\\1142710\\<workshop_id>\\<file>.pack`, so the id is the parent directory name when its parent is the TW3 appid folder.

    Args:
        path: `.pack` file path, or None.

    Returns:
        Workshop id, or None when the path is empty or does not match the convention.
    """
    if not path or not isinstance(path, str):
        return None
    parts = PurePath(path).parts
    if len(parts) < 3:
        return None
    if parts[-3] != _TW3_APPID_FOLDER:
        return None
    return parts[-2]


@contextmanager
def _sys_path_prepended(directory: Path) -> Iterator[None]:
    """Prepend `directory` to `sys.path` for the duration of the context.

    Args:
        directory: Path to insert at index 0.
    """
    entry = str(directory)
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        try:
            sys.path.remove(entry)
        except ValueError:
            pass


class HelperScriptsLoaderError(Exception):
    """Base for all loader errors."""


class HelperScriptsNotConfiguredError(HelperScriptsLoaderError):
    """The configured `helper_scripts_path` is unset or does not exist on disk."""


class RegistryFileMissingError(HelperScriptsLoaderError):
    """The expected .py file is not present in the configured directory."""


class RegistryConstantNotFoundError(HelperScriptsLoaderError):
    """The .py file loaded but does not declare the expected constant."""


class RegistryFileSyntaxError(HelperScriptsLoaderError):
    """The .py file failed to compile."""


def _load_constant(helper_scripts_path: Path, filename: str, constant: str) -> Any:
    """Live-import `filename` from `helper_scripts_path` and return its `constant` attribute.

    Args:
        helper_scripts_path: Configured `helper_scripts/` directory.
        filename: .py file relative to `helper_scripts_path`.
        constant: Module-level constant to read.

    Returns:
        The constant's value.
    """
    if not helper_scripts_path or not helper_scripts_path.is_dir():
        raise HelperScriptsNotConfiguredError(str(helper_scripts_path))

    target = helper_scripts_path / filename
    if not target.is_file():
        raise RegistryFileMissingError(str(target))

    module_name = "_helper_scripts_" + filename.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        raise RegistryFileSyntaxError(f"could not build module spec for {target}")

    module = importlib.util.module_from_spec(spec)
    try:
        with _sys_path_prepended(helper_scripts_path):
            spec.loader.exec_module(module)
    except SyntaxError as exc:
        raise RegistryFileSyntaxError(str(exc)) from exc

    if not hasattr(module, constant):
        raise RegistryConstantNotFoundError(f"{filename} has no '{constant}' attribute")
    return getattr(module, constant)


def load_supported_mods(helper_scripts_path: Path) -> list[dict]:
    """Live-import `SUPPORTED_MODS` from `data/supported_mods.py`.

    Args:
        helper_scripts_path: Configured `helper_scripts/` directory.

    Returns:
        `SUPPORTED_MODS` dicts, each with a derived `workshop_id` (None when the path does not follow the TW3 convention).
    """
    mods = _load_constant(helper_scripts_path, SUPPORTED_MODS_FILE, "SUPPORTED_MODS")
    for mod in mods:
        mod["workshop_id"] = _derive_workshop_id(mod.get("path"))
    return mods


def load_supported_effects(helper_scripts_path: Path) -> dict:
    """Live-import `SUPPORTED_EFFECTS` from `data/dynamic_rors_effects.py`.

    Args:
        helper_scripts_path: Configured `helper_scripts/` directory.

    Returns:
        The `SUPPORTED_EFFECTS` dict.
    """
    return _load_constant(helper_scripts_path, SUPPORTED_EFFECTS_FILE, "SUPPORTED_EFFECTS")


def supported_mods_source_path(helper_scripts_path: Path) -> Path:
    """Return the path to `data/supported_mods.py` inside helper_scripts.

    Args:
        helper_scripts_path: Configured `helper_scripts/` directory.

    Returns:
        Path to the file, which may not exist.
    """
    return helper_scripts_path / SUPPORTED_MODS_FILE


def load_supported_effects_categories(helper_scripts_path: Path) -> list[str]:
    """Return the sorted top-level category names from `SUPPORTED_EFFECTS`.

    Args:
        helper_scripts_path: Configured `helper_scripts/` directory.

    Returns:
        Sorted top-level keys.
    """
    effects = load_supported_effects(helper_scripts_path)
    return sorted(effects.keys())
