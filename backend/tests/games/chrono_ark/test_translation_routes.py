"""Chrono Ark translation routes."""

import json
from pathlib import Path

import pytest
from backend.games.base import ModInfo
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.chrono_ark.routes import translation as ca_translation
from backend.models import LocString
from fastapi.testclient import TestClient

FAKE_MOD = ModInfo(mod_id="900000002", name="Fake Mod", author="Tester", path=Path("fake"))


class _FakeProvider:
    """Records the target language of every estimate."""

    name = "fake"

    def __init__(self):
        self.target_langs: list[str] = []

    def estimate_cost(self, entries, **kwargs):
        """Record the call and return a fixed estimate.

        Args:
            entries: `(key, text)` pairs to estimate.
            **kwargs: Prompt parts, including `target_lang`.

        Returns:
            A fixed estimate dict.
        """
        self.target_langs.append(kwargs["target_lang"])
        return {"cost": 0.0, "strings": len(entries)}


@pytest.fixture
def fake_ca(monkeypatch):
    """Give the Chrono Ark adapter one fake mod with one Korean string, and a fake provider.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The fake provider.
    """
    provider = _FakeProvider()
    strings = {"Buff/B_Test_Name": LocString(key="Buff/B_Test_Name", type="Text", desc="", translations={"Korean": "테스트"})}
    monkeypatch.setattr(ChronoArkAdapter, "scan_mods", lambda self, search_path=None: [FAKE_MOD])
    monkeypatch.setattr(ChronoArkAdapter, "extract_strings", lambda self, path: (strings, {}))
    monkeypatch.setattr(ca_translation, "get_provider", lambda name: provider)
    monkeypatch.setattr(ca_translation, "load_glossary", lambda: {})
    monkeypatch.setattr(ca_translation, "load_mod_glossary", lambda mod_id: {})
    monkeypatch.setattr(ca_translation, "load_character_context", lambda mod_id: {})
    monkeypatch.setattr(ca_translation, "load_source_language_override", lambda mod_id: None)
    monkeypatch.setattr(ca_translation, "load_target_language_override", lambda mod_id: "Spanish")
    return provider


def test_estimate_all_streams_an_estimate_per_mod(fake_ca):
    from backend.web_server import app

    res = TestClient(app).post("/api/games/chrono_ark/translate/estimate-all")

    assert res.status_code == 200
    events = [json.loads(line[len("data: ") :]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0]["mod_id"] == FAKE_MOD.mod_id
    assert events[0]["estimates"]["Korean"]["strings"] == 1
    assert events[-1] == {"done": True}
    assert fake_ca.target_langs == ["Spanish"]


def test_get_provider_raises_for_unknown_names():
    from backend.main import get_provider

    with pytest.raises(ValueError, match="nope"):
        get_provider("nope")


def test_get_provider_builds_the_manual_provider():
    from backend.main import get_provider

    assert get_provider("manual").name == "Manual"


@pytest.mark.parametrize("name", ["manual", "nope"])
def test_web_routes_reject_providers_they_cannot_run(name):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        ca_translation._web_provider(name)
    assert exc.value.status_code == 400
