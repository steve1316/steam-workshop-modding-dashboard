"""FastAPI backend for the Steam Workshop Modding Dashboard, with routes organized under `backend.routes`."""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.settings import settings
from backend.games.registry import get_adapter, list_games
from backend.routes import llamacpp, ollama, steamcmd
from backend.routes import settings as settings_routes
from backend.routes.helpers import chrono_ark_adapter
from backend.scripts.migrate_storage_v1_to_v2 import run_migration
from backend.scripts.migrate_storage_v2_to_v3 import run_migration as run_migration_v2_to_v3


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run storage migrations on startup, which are no-ops once the marker file exists."""
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

# Game-agnostic routers stay flat under /api/.
app.include_router(ollama.router)
app.include_router(llamacpp.router)
app.include_router(settings_routes.router)
app.include_router(steamcmd.router)

# Adapter routers mount under /api/games/<id>/.
for _game_id in list_games():
    _adapter_instance = get_adapter(_game_id)
    app.include_router(_adapter_instance.router)


def _mount_workshop(target: FastAPI) -> None:
    """Serve Chrono Ark's workshop folder at /api/workshop for mod preview images.

    Args:
        target: The app to mount on.
    """
    # Only Chrono Ark links /workshop/ thumbnails, so this must not follow whichever game was active at startup.
    workshop_path = chrono_ark_adapter()._WORKSHOP_PATH
    if Path(workshop_path).exists():
        target.mount("/api/workshop", StaticFiles(directory=str(workshop_path)), name="workshop")


# Mounted last because a mount shadows any route registered after it.
_mount_workshop(app)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=settings.api_port,
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
