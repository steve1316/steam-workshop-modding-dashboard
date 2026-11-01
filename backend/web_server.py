"""
FastAPI backend for the Steam Workshop Modding Dashboard.

Provides REST APIs for mod discovery, string extraction, translation status,
glossary management, and triggering translation jobs. Routes are organized
into domain-specific modules under `backend.routes`.
"""

import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend import config
from backend.routes.helpers import _adapter
from backend.routes import ollama, llamacpp, settings, steamcmd
from backend.games.registry import list_games, get_adapter
from backend.scripts.migrate_storage_v1_to_v2 import run_migration
from backend.scripts.migrate_storage_v2_to_v3 import run_migration as run_migration_v2_to_v3


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """App lifespan hooks. Runs storage migration on startup.

    Idempotent: the migration marker file makes subsequent migration runs a no-op.
    """
    run_migration()
    run_migration_v2_to_v3()
    yield


app = FastAPI(title="Steam Workshop Modding Dashboard API", lifespan=lifespan)


# Only the local dashboard may call the API, so other sites open in the browser cannot read or change mod data.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register game-agnostic routers (kept flat under /api/...).
app.include_router(ollama.router)
app.include_router(llamacpp.router)
app.include_router(settings.router)
app.include_router(steamcmd.router)

# Mount each registered adapter's router under /api/games/<id>/...
for _game_id in list_games():
    _adapter_instance = get_adapter(_game_id)
    app.include_router(_adapter_instance.router)

# Mount the workshop directory as static files so preview images are served
# directly without going through a Python endpoint for each request.
# This must be after all route definitions since mounts take priority over
# routes defined after them.
_workshop_path = getattr(_adapter, "_WORKSHOP_PATH", None)
if _workshop_path and Path(_workshop_path).exists():
    app.mount("/api/workshop", StaticFiles(directory=str(_workshop_path)), name="workshop")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=config.API_PORT,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"fmt": "%(asctime)s %(levelprefix)s %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S", "use_colors": True, "()": "uvicorn.logging.DefaultFormatter"},
                "access": {
                    "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                    "use_colors": True,
                    "()": "uvicorn.logging.AccessFormatter",
                },
            },
            "handlers": {
                "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stderr"},
                "access": {"formatter": "access", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
            },
        },
    )
