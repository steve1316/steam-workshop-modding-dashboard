"""Filesystem path helpers."""

from pathlib import Path


def safe_child(base: Path, name: str) -> Path:
    """Join a single user-supplied name onto `base`, rejecting anything that could point outside it.

    Args:
        base: The directory the name must stay inside.
        name: A bare file or folder name, such as a backup id from a URL.

    Returns:
        The joined path.
    """
    # Backslashes and drive colons matter too, since Windows treats them as separators.
    if name in ("", ".", "..") or any(c in name for c in "/\\:"):
        raise ValueError(f"Invalid name: {name!r}")
    return base / name
