"""CORS only lets the local dashboard call the API."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app


def _preflight(origin: str):
    """Send a CORS preflight from the given origin.

    Args:
        origin: The `Origin` header to send.

    Returns:
        The test client response.
    """
    return TestClient(app).options("/api/settings", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:4173", "http://localhost"])
def test_local_origins_are_allowed(origin):
    res = _preflight(origin)
    assert res.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost.evil.example:5173", "http://192.168.1.5:5173"])
def test_other_origins_are_rejected(origin):
    res = _preflight(origin)
    assert "access-control-allow-origin" not in res.headers
