"""Game adapter registry: register and look up adapters by id."""

from backend.games.base import GameAdapter
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.total_war_warhammer_3.adapter import TotalWarWarhammer3Adapter

_ADAPTERS: dict[str, type[GameAdapter]] = {
    "chrono_ark": ChronoArkAdapter,
    "total_war_warhammer_3": TotalWarWarhammer3Adapter,
}


def register_adapter(game_id: str, adapter_class: type[GameAdapter]) -> None:
    """Register a game adapter class.

    Args:
        game_id: Game id (e.g. `"chrono_ark"`).
        adapter_class: Adapter class to register.
    """
    _ADAPTERS[game_id] = adapter_class


def get_adapter(game_id: str) -> GameAdapter:
    """Create and return a game adapter instance by ID.

    Args:
        game_id: Game id.

    Returns:
        New adapter instance.
    """
    if game_id not in _ADAPTERS:
        available = ", ".join(_ADAPTERS.keys()) or "(none)"
        raise ValueError(f"Unknown game: {game_id}. Available: {available}")
    return _ADAPTERS[game_id]()


def list_games() -> list[str]:
    """Return all registered game ids."""
    return list(_ADAPTERS.keys())


def list_games_metadata() -> list[dict]:
    """Return chassis metadata for every registered adapter.

    Returns:
        Dicts with `game_id`, `display_name`, `icon`, `capabilities`.
    """
    result = []
    for adapter_class in _ADAPTERS.values():
        instance = adapter_class()
        result.append(
            {
                "game_id": instance.game_id,
                "display_name": instance.display_name,
                "icon": instance.icon,
                "capabilities": instance.capabilities,
            }
        )
    return result
