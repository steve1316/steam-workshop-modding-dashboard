"""Where WH3 files live: helper_scripts, rpfm_cli, the Steam Workshop folders and the parent pack cache."""

from __future__ import annotations

from pathlib import Path

from backend.core.paths import game_storage_path
from backend.core.settings import settings
from backend.games.total_war_warhammer_3 import GAME_ID


def helper_scripts_path() -> Path:
    """Resolve the helper_scripts directory from `settings.tw3.helper_path`.

    Returns:
        Path that may not exist, since loaders validate it.
    """
    return Path(settings.tw3.helper_path or "")


def rpfm_cli_candidate(rpfm_cli_path: str, helper_path: str) -> Path | None:
    """Return where `rpfm_cli` should be: `rpfm_cli_path` if set, else `rpfm_cli.exe` in `helper_path`.

    Args:
        rpfm_cli_path: Configured `rpfm_cli` path, blank when unset.
        helper_path: Configured helper_scripts dir, blank when unset.

    Returns:
        Candidate path that may not exist, or `None` when both are blank.
    """
    if rpfm_cli_path:
        return Path(rpfm_cli_path)
    return Path(helper_path) / "rpfm_cli.exe" if helper_path else None


def resolve_rpfm_cli_path() -> Path | None:
    """Resolve `rpfm_cli` from `settings.tw3`.

    Returns:
        Path when it resolves to a file, else `None`.
    """
    rpfm = rpfm_cli_candidate(settings.tw3.rpfm_cli_path or "", settings.tw3.helper_path or "")
    return rpfm if rpfm is not None and rpfm.is_file() else None


TW3_APPID = "1142710"


def tw3_workshop_content_dir(workshop_id: str) -> Path | None:
    """Resolve the local Steam Workshop folder for a TW3 workshop item.

    Builds `<steam_library_drive>\\SteamLibrary\\steamapps\\workshop\\content\\1142710\\<workshop_id>`
    from `settings.tw3.steam_library_drive`. The folder may not exist on disk, so callers should validate.

    Args:
        workshop_id: Numeric Workshop item id, which the caller sanitizes.

    Returns:
        Workshop content directory, or `None` when the Steam library drive setting is empty.
    """
    workshop_dir = _tw3_workshop_dir()
    return None if workshop_dir is None else workshop_dir / "content" / TW3_APPID / workshop_id


def tw3_workshop_manifest_path() -> Path | None:
    """Resolve Steam's TW3 Workshop manifest, which records when each subscribed item was last updated.

    Returns:
        `<steam_library_drive>\\SteamLibrary\\steamapps\\workshop\\appworkshop_1142710.acf`, or `None` when the drive setting is empty. It may not exist.
    """
    workshop_dir = _tw3_workshop_dir()
    return None if workshop_dir is None else workshop_dir / f"appworkshop_{TW3_APPID}.acf"


def _tw3_workshop_dir() -> Path | None:
    """Resolve the Steam library's Workshop folder from `settings.tw3.steam_library_drive`.

    Returns:
        `<steam_library_drive>\\SteamLibrary\\steamapps\\workshop`, or `None` when the Steam library drive setting is empty.
    """
    drive = (settings.tw3.steam_library_drive or "").strip()
    if not drive:
        return None
    # A bare drive spec like "F:" is drive-relative on Windows. Promote it to "F:\" so the join is absolute.
    if len(drive) == 2 and drive.endswith(":"):
        drive = drive + "\\"
    return Path(drive) / "SteamLibrary" / "steamapps" / "workshop"


def parent_pack_cache_dir(parent_workshop_id: str) -> Path:
    """Return the per-parent RPFM extract cache dir.

    Args:
        parent_workshop_id: Workshop id of the parent pack.

    Returns:
        Cache directory.
    """
    return game_storage_path(GAME_ID) / "parent_pack_cache" / parent_workshop_id
