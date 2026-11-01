"""Ollama-related API endpoints for the Steam Workshop Modding Dashboard."""

import asyncio
import os
import shutil
import subprocess
import tempfile
import urllib.request

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend import config
from backend.process_manager import start_process, stop_process, is_managed
from backend.routes.models import OllamaPullRequest

router = APIRouter(prefix="/api/ollama")


async def _check_ollama_status() -> str:
    """Check if Ollama is installed and running.

    Returns:
        `"running"` if the API responds, `"stopped"` if the binary is on PATH but the API is unreachable, else `"not_installed"`.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=1.0)
        if resp.status_code == 200:
            return "running"
        return "stopped"
    except httpx.ConnectError:
        if shutil.which("ollama") is not None:
            return "stopped"
        return "not_installed"
    except Exception:
        return "stopped"


@router.get("/status")
async def get_ollama_status():
    """Check Ollama installation status and list available models.

    Returns:
        `status`, `models`, `base_url`, and `managed`.
    """
    status = await _check_ollama_status()
    models: list[dict] = []
    if status == "running":
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [{"name": m["name"], "size": m.get("size", 0), "modified_at": m.get("modified_at", "")} for m in data.get("models", [])]
        except Exception:
            pass
    return {"status": status, "models": models, "base_url": config.OLLAMA_BASE_URL, "managed": is_managed("ollama")}


@router.get("/models")
async def get_ollama_models():
    """List models currently downloaded in Ollama.

    Returns:
        `models` list.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            return {"models": data.get("models", [])}
        raise HTTPException(502, "Ollama returned non-200 status")
    except httpx.ConnectError:
        raise HTTPException(503, "Cannot connect to Ollama. Is it running?")


@router.post("/pull")
async def pull_ollama_model(req: OllamaPullRequest):
    """Pull (download) an Ollama model with streaming progress via SSE.

    Args:
        req: Model name to pull.

    Returns:
        SSE progress stream.
    """

    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{config.OLLAMA_BASE_URL}/api/pull",
                json={"name": req.model, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        yield f"data: {line}\n\n"
        yield 'data: {"status": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/install")
async def install_ollama():
    """Download and launch the official Ollama Windows installer.

    Returns:
        `success` and `message`.
    """
    if await _check_ollama_status() == "running":
        return {"success": True, "message": "Ollama is already installed and running."}

    try:
        installer_url = "https://ollama.com/download/OllamaSetup.exe"
        temp_dir = tempfile.mkdtemp()
        installer_path = os.path.join(temp_dir, "OllamaSetup.exe")

        await asyncio.to_thread(urllib.request.urlretrieve, installer_url, installer_path)

        subprocess.Popen([installer_path], shell=False)

        return {"success": True, "message": "Installer launched. Complete the installation wizard, then check status again."}
    except Exception as e:
        raise HTTPException(500, f"Failed to download/launch installer: {e}")


@router.post("/start")
async def start_ollama():
    """Start `ollama serve` as a managed background process.

    Returns:
        `success`, `message`, and `managed`.
    """
    status = await _check_ollama_status()
    if status == "running":
        return {"success": True, "message": "Ollama is already running.", "managed": is_managed("ollama")}
    if status == "not_installed":
        raise HTTPException(400, "Ollama is not installed. Install it first.")

    log_dir = config.STORAGE_PATH / "logs"
    success, message = await asyncio.to_thread(start_process, "ollama", ["ollama", "serve"], log_dir)
    if not success:
        raise HTTPException(500, message)

    for _ in range(10):
        await asyncio.sleep(0.5)
        if await _check_ollama_status() == "running":
            return {"success": True, "message": message, "managed": True}

    return {"success": True, "message": message + " (server may still be starting)", "managed": True}


@router.post("/stop")
async def stop_ollama():
    """Stop a managed Ollama process.

    Returns:
        `success` and `message`.
    """
    if not is_managed("ollama"):
        raise HTTPException(400, "Ollama was not started by this app. Stop it manually.")
    success, message = await asyncio.to_thread(stop_process, "ollama")
    if not success:
        raise HTTPException(500, message)
    return {"success": True, "message": message}
