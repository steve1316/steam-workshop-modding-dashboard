import pytest
from fastapi import HTTPException

from backend.providers.factory import get_provider
from backend.routes.web_provider import web_provider


def test_get_provider_raises_for_unknown_names():
    with pytest.raises(ValueError, match="nope"):
        get_provider("nope")


def test_get_provider_builds_the_manual_provider():
    assert get_provider("manual").name == "Manual"


@pytest.mark.parametrize("name", ["manual", "nope"])
def test_web_routes_reject_providers_they_cannot_run(name):
    with pytest.raises(HTTPException) as exc:
        web_provider(name)
    assert exc.value.status_code == 400
