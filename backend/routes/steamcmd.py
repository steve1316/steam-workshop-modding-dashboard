"""HTTP routes for installing the bundled SteamCMD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import config
from backend.routes.helpers import _update_env_file
from backend.steamcmd_installer import install_steamcmd

router = APIRouter(prefix="/api/steamcmd")


@router.post("/install")
async def post_steamcmd_install():
    """Download SteamCMD into `<STORAGE_PATH>/steamcmd` and persist the resolved path.

    Re-running overwrites existing files. The user must still run `steamcmd +login <username>` once in a terminal to seed the Steam Guard
    sentry file before publishes succeed.

    Returns:
        `{"path": str}` to the installed `steamcmd.exe`.
    """
    target_dir = config.STORAGE_PATH / "steamcmd"
    try:
        steamcmd_exe = await install_steamcmd(target_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SteamCMD install failed: {exc}")

    path_str = str(steamcmd_exe)
    config.STEAMCMD_PATH = path_str
    _update_env_file({"SWMT_STEAMCMD_PATH": path_str})
    return {"path": path_str}
