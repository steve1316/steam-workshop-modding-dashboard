"""llama.cpp-related API endpoints for the Steam Workshop Modding Dashboard."""

import asyncio
import json
import os
import shutil
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend import config
from backend.process_manager import is_managed, start_process, stop_process
from backend.routes.helpers import _gguf_download_cancels, _update_env_file
from backend.routes.models import GGUFDownloadRequest, LlamaCppInstallRequest

router = APIRouter(prefix="/api/llamacpp")

# GPU backend options for llama-server binary downloads.
_LLAMACPP_BACKENDS = {
    "cuda-13": {"label": "NVIDIA GPU (CUDA 13.1 — RTX 40/50 series)", "zip_pattern": "bin-win-cuda-13.1-x64", "cudart_pattern": "cudart-llama-bin-win-cuda-13.1-x64"},
    "cuda-12": {"label": "NVIDIA GPU (CUDA 12.4 — RTX 20/30 series)", "zip_pattern": "bin-win-cuda-12.4-x64", "cudart_pattern": "cudart-llama-bin-win-cuda-12.4-x64"},
    "vulkan": {"label": "Any GPU (Vulkan)", "zip_pattern": "bin-win-vulkan-x64", "cudart_pattern": None},
    "cpu": {"label": "CPU only", "zip_pattern": "bin-win-cpu-x64", "cudart_pattern": None},
}


def _llamacpp_binary() -> Path | None:
    """Locate the llama-server binary via the configured path, then `storage/bin/`, then PATH.

    Returns:
        Executable path, or None if not found.
    """
    configured = Path(config.LLAMACPP_BINARY_PATH)
    if configured.is_file():
        return configured
    managed = config.STORAGE_PATH / "bin" / "llama-server.exe"
    if managed.is_file():
        return managed
    found = shutil.which("llama-server")
    if found:
        return Path(found)
    return None


async def _ensure_llamacpp_running() -> None:
    """Start llama-server if it isn't already healthy, so translation doesn't need a manual start."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{config.LLAMACPP_BASE_URL}/health", timeout=2.0)
        if resp.status_code == 200:
            return
    except Exception:
        pass

    model_path = config.LLAMACPP_MODEL_PATH
    if not model_path:
        raise HTTPException(400, "Model path is required. Select and download a model first.")

    binary = _llamacpp_binary()
    if not binary:
        raise HTTPException(400, "llama-server is not installed. Install it first.")

    from urllib.parse import urlparse

    parsed = urlparse(config.LLAMACPP_BASE_URL)
    port = str(parsed.port or 8080)

    ctx_size = config.LLAMACPP_CTX_SIZE

    args = [
        str(binary),
        "--model",
        model_path,
        "--port",
        port,
        "--n-gpu-layers",
        str(config.LLAMACPP_GPU_LAYERS),
        "--ctx-size",
        str(ctx_size),
    ]

    log_dir = config.STORAGE_PATH / "logs"
    success, message = await asyncio.to_thread(start_process, "llamacpp", args, log_dir)
    if not success:
        raise HTTPException(500, message)

    # llama-server can take a while to load models.
    for _ in range(60):
        await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{config.LLAMACPP_BASE_URL}/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except Exception:
            if not is_managed("llamacpp"):
                raise HTTPException(500, "llama-server exited unexpectedly. Check logs in storage/logs/.")

    raise HTTPException(500, "llama-server did not become healthy within 60 seconds.")


@router.get("/status")
async def get_llamacpp_status():
    """Check whether llama-server is reachable and installed.

    Returns:
        `status`, `installed`, `binary_path`, `base_url`, and `managed`.
    """
    installed = _llamacpp_binary() is not None
    running = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{config.LLAMACPP_BASE_URL}/health", timeout=2.0)
        if resp.status_code == 200:
            running = True
    except Exception:
        pass
    return {
        "status": "running" if running else "not_running",
        "installed": installed,
        "binary_path": str(_llamacpp_binary() or ""),
        "base_url": config.LLAMACPP_BASE_URL,
        "managed": is_managed("llamacpp"),
    }


@router.post("/install")
async def install_llamacpp(req: LlamaCppInstallRequest):
    """Download and extract llama-server from the latest GitHub release with SSE progress.

    Args:
        req: GPU backend to download.

    Returns:
        SSE progress stream.
    """
    if req.backend not in _LLAMACPP_BACKENDS:
        raise HTTPException(400, f"Invalid backend: {req.backend}. Choose from: {', '.join(_LLAMACPP_BACKENDS)}")

    backend_info = _LLAMACPP_BACKENDS[req.backend]
    bin_dir = config.STORAGE_PATH / "bin"

    async def event_stream():
        import io
        import zipfile

        try:
            yield f"data: {json.dumps({'status': 'fetching_release'})}\n\n"

            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, read=None), headers={"User-Agent": "curl/8.0"}) as client:
                r = await client.get("https://api.github.com/repos/ggerganov/llama.cpp/releases/latest")
                if r.status_code != 200:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'GitHub API error: HTTP {r.status_code}'})}\n\n"
                    return
                release = r.json()
                tag = release["tag_name"]
                assets = release.get("assets", [])

                # Exclude cudart zips, which are a separate download.
                zip_asset = next((a for a in assets if backend_info["zip_pattern"] in a["name"] and a["name"].endswith(".zip") and not a["name"].startswith("cudart")), None)
                if not zip_asset:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'No {backend_info["label"]} build found in release {tag}'})}\n\n"
                    return

                zip_url = zip_asset["browser_download_url"]
                zip_total = zip_asset["size"]
                yield f"data: {json.dumps({'status': 'downloading', 'file': zip_asset['name'], 'completed': 0, 'total': zip_total})}\n\n"

                zip_data = bytearray()
                async with client.stream("GET", zip_url) as resp:
                    async for chunk in resp.aiter_bytes(1024 * 1024):
                        zip_data.extend(chunk)
                        if len(zip_data) % (5 * 1024 * 1024) < 1024 * 1024:
                            yield f"data: {json.dumps({'status': 'downloading', 'file': zip_asset['name'], 'completed': len(zip_data), 'total': zip_total})}\n\n"
                yield f"data: {json.dumps({'status': 'downloading', 'file': zip_asset['name'], 'completed': len(zip_data), 'total': zip_total})}\n\n"

                cudart_data = None
                if backend_info["cudart_pattern"]:
                    cudart_asset = next((a for a in assets if backend_info["cudart_pattern"] in a["name"] and a["name"].endswith(".zip")), None)
                    if cudart_asset:
                        cudart_url = cudart_asset["browser_download_url"]
                        cudart_total = cudart_asset["size"]
                        yield f"data: {json.dumps({'status': 'downloading', 'file': cudart_asset['name'], 'completed': 0, 'total': cudart_total})}\n\n"
                        cudart_data = bytearray()
                        async with client.stream("GET", cudart_url) as resp:
                            async for chunk in resp.aiter_bytes(1024 * 1024):
                                cudart_data.extend(chunk)
                                if len(cudart_data) % (10 * 1024 * 1024) < 1024 * 1024:
                                    yield f"data: {json.dumps({'status': 'downloading', 'file': cudart_asset['name'], 'completed': len(cudart_data), 'total': cudart_total})}\n\n"
                        yield f"data: {json.dumps({'status': 'downloading', 'file': cudart_asset['name'], 'completed': len(cudart_data), 'total': cudart_total})}\n\n"

            yield f"data: {json.dumps({'status': 'extracting'})}\n\n"
            bin_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                for member in zf.namelist():
                    if member.endswith((".exe", ".dll")):
                        filename = os.path.basename(member)
                        target = bin_dir / filename
                        target.write_bytes(zf.read(member))

            if cudart_data:
                with zipfile.ZipFile(io.BytesIO(cudart_data)) as zf:
                    for member in zf.namelist():
                        if member.endswith(".dll"):
                            filename = os.path.basename(member)
                            target = bin_dir / filename
                            if not target.exists():
                                target.write_bytes(zf.read(member))

            binary_path = str(bin_dir / "llama-server.exe")
            config.LLAMACPP_BINARY_PATH = binary_path
            _update_env_file({"SWMT_LLAMACPP_BINARY_PATH": binary_path})

            print(f"[llamacpp] Installed {tag} ({backend_info['label']}) to {bin_dir}")
            yield f"data: {json.dumps({'status': 'done', 'tag': tag, 'binary_path': binary_path})}\n\n"

        except Exception as e:
            print(f"[llamacpp] Install error: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/start")
async def start_llamacpp():
    """Start llama-server as a managed background process.

    Returns:
        `success` and `managed`.
    """
    await _ensure_llamacpp_running()
    return {"success": True, "managed": is_managed("llamacpp")}


@router.post("/stop")
async def stop_llamacpp():
    """Stop a managed llama-server process.

    Returns:
        `success` and `message`.
    """
    if not is_managed("llamacpp"):
        raise HTTPException(400, "llama-server was not started by this app. Stop it manually.")
    success, message = await asyncio.to_thread(stop_process, "llamacpp")
    if not success:
        raise HTTPException(500, message)
    return {"success": True, "message": message}


@router.get("/models")
async def list_llamacpp_models():
    """List GGUF model files in the local models directory.

    Returns:
        `models` list and `models_dir`.
    """
    models_dir = config.LLAMACPP_MODELS_DIR
    if not models_dir.exists():
        return {"models": [], "models_dir": str(models_dir)}
    models = []
    for f in sorted(models_dir.glob("*.gguf")):
        models.append({"name": f.name, "path": str(f), "size": f.stat().st_size})
    return {"models": models, "models_dir": str(models_dir)}


@router.post("/download")
async def download_gguf_model(req: GGUFDownloadRequest):
    """Download a GGUF model file from a URL with streaming progress via SSE.

    Args:
        req: URL and target filename.

    Returns:
        SSE progress stream.
    """
    models_dir = config.LLAMACPP_MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)
    dest = models_dir / req.filename

    cancel_event = asyncio.Event()
    _gguf_download_cancels[req.filename] = cancel_event

    async def event_stream():
        try:
            if dest.is_file():
                print(f"[gguf] Already exists: {dest}")
                yield f"data: {json.dumps({'status': 'done', 'path': str(dest), 'completed': 0, 'total': 0})}\n\n"
                return

            print(f"[gguf] Starting download: {req.url}")
            print(f"[gguf] Destination: {dest}")
            yield f"data: {json.dumps({'status': 'connecting'})}\n\n"

            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None), follow_redirects=True) as client:
                async with client.stream("GET", req.url) as response:
                    print(f"[gguf] Connected: HTTP {response.status_code}, Content-Length: {response.headers.get('content-length', 'unknown')}")
                    if response.status_code != 200:
                        yield f"data: {json.dumps({'status': 'error', 'message': f'HTTP {response.status_code}'})}\n\n"
                        return

                    total = int(response.headers.get("content-length", 0))
                    completed = 0
                    last_report = 0
                    yield f"data: {json.dumps({'status': 'downloading', 'completed': 0, 'total': total})}\n\n"

                    partial = dest.parent / (dest.name + ".part")
                    with open(partial, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                            if cancel_event.is_set():
                                yield f"data: {json.dumps({'status': 'cancelled'})}\n\n"
                                partial.unlink(missing_ok=True)
                                return

                            f.write(chunk)
                            completed += len(chunk)

                            if completed - last_report >= 2 * 1024 * 1024 or completed == total:
                                yield f"data: {json.dumps({'status': 'downloading', 'completed': completed, 'total': total})}\n\n"
                                last_report = completed

                    partial.rename(dest)
                    print(f"[gguf] Download complete: {dest} ({completed} bytes)")
                    yield f"data: {json.dumps({'status': 'done', 'path': str(dest), 'completed': completed, 'total': total})}\n\n"
        except Exception as e:
            print(f"[gguf] Error: {e}")
            (dest.parent / (dest.name + ".part")).unlink(missing_ok=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            _gguf_download_cancels.pop(req.filename, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/download/cancel")
async def cancel_gguf_download(req: GGUFDownloadRequest):
    """Cancel an in-progress GGUF download.

    Args:
        req: Identifies the file to cancel.

    Returns:
        `success`, plus `message` on failure.
    """
    event = _gguf_download_cancels.get(req.filename)
    if event:
        event.set()
        return {"success": True}
    return {"success": False, "message": "No active download for this file."}


@router.delete("/models/{filename}")
async def delete_llamacpp_model(filename: str):
    """Delete a downloaded GGUF model file.

    Args:
        filename: GGUF file to delete.

    Returns:
        `success` and `message`.
    """
    models_dir = config.LLAMACPP_MODELS_DIR
    target = models_dir / filename
    if not target.exists():
        raise HTTPException(404, f"Model not found: {filename}")
    # Blocks path traversal out of the models directory.
    if not target.resolve().parent == models_dir.resolve():
        raise HTTPException(400, "Invalid filename.")
    target.unlink()
    return {"success": True, "message": f"Deleted {filename}"}
