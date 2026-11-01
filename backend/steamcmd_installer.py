"""Downloads and extracts Valve's SteamCMD zip (~5MB bootstrap) for the Publish to Workshop feature.

SteamCMD self-updates the rest of its files (~250MB) on first launch.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx

STEAMCMD_DOWNLOAD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"


async def install_steamcmd(target_dir: Path) -> Path:
    """Download `steamcmd.zip` from Valve's CDN and extract it into `target_dir`.

    Creates the directory if missing and overwrites existing files, so re-running is safe.

    Args:
        target_dir: Install directory (e.g. `backend/storage/steamcmd`).

    Returns:
        Path to `steamcmd.exe`.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(STEAMCMD_DOWNLOAD_URL)
    if resp.status_code != 200:
        raise RuntimeError(f"download failed: HTTP {resp.status_code}")

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(target_dir)
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"downloaded archive is not a valid zip: {exc}")

    steamcmd_exe = target_dir / "steamcmd.exe"
    if not steamcmd_exe.is_file():
        raise RuntimeError("extracted archive does not contain steamcmd.exe")
    return steamcmd_exe
