"""Chrono Ark translation routes."""

import json
from pathlib import Path

import pytest
from backend.games.base import ModInfo
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.chrono_ark.routes import translation as ca_translation
from backend.games.chrono_ark.services import translation as ca_services
from backend.models import LocString
from backend.routes import web_provider as web_provider_module
from fastapi.testclient import TestClient

FAKE_MOD = ModInfo(mod_id="900000002", name="Fake Mod", author="Tester", path=Path("fake"))


class _FakeProvider:
    """Records the target language of every estimate and prompt."""

    name = "fake"

    def __init__(self):
        self.target_langs: list[str] = []
        self.prompt_kwargs: list[dict] = []

    def build_prompt(self, entries, **kwargs):
        """Record the prompt parts and return canned prompts.

        Args:
            entries: `(key, text)` pairs in the batch.
            **kwargs: Prompt parts.

        Returns:
            A system prompt naming the languages and a user message listing the keys.
        """
        self.prompt_kwargs.append(kwargs)
        return f"{kwargs['source_lang']}->{kwargs['target_lang']}", ",".join(k for k, _ in entries)

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
    monkeypatch.setattr(ChronoArkAdapter, "find_mod", lambda self, mod_id, search_path=None: FAKE_MOD if mod_id == FAKE_MOD.mod_id else None)
    monkeypatch.setattr(ChronoArkAdapter, "extract_strings", lambda self, path: (strings, {}))
    monkeypatch.setattr(web_provider_module, "get_provider", lambda name: provider)
    monkeypatch.setattr(ca_translation, "load_glossary", lambda path: {})
    monkeypatch.setattr(ca_services, "load_mod_glossary", lambda mod_id, game_id: {})
    monkeypatch.setattr(ca_services, "load_character_context", lambda mod_id, game_id: {})
    monkeypatch.setattr(ca_translation, "load_source_language_override", lambda mod_id, game_id: None)
    monkeypatch.setattr(ca_translation, "load_target_language_override", lambda mod_id, game_id: "Spanish")
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


def test_preview_plans_batches_for_the_untranslated_strings(fake_ca):
    from backend.web_server import app

    res = TestClient(app).post("/api/games/chrono_ark/translate/preview", json={"mod_id": FAKE_MOD.mod_id})

    assert res.status_code == 200
    body = res.json()
    assert body["total_strings"] == 1
    assert body["total_batches"] == 1
    assert body["provider"] == "fake"
    assert body["batch_plan"] == [{"source_lang": "Korean", "keys": ["Buff/B_Test_Name"], "size": 1}]
    assert body["previews"]["Korean"]["system_prompt"] == "Korean->Spanish"
    assert body["estimates"]["Korean"]["strings"] == 1
    assert fake_ca.prompt_kwargs[0]["game_context"]


def test_preview_reports_nothing_to_do_when_every_string_is_translated(fake_ca, monkeypatch):
    from backend.web_server import app

    monkeypatch.setattr(ca_translation, "load_translations", lambda mod_id, game_id: {"Buff/B_Test_Name": "Prueba"})
    res = TestClient(app).post("/api/games/chrono_ark/translate/preview", json={"mod_id": FAKE_MOD.mod_id})

    assert res.status_code == 200
    assert res.json()["total_strings"] == 0


def test_system_prompt_uses_the_requested_languages(fake_ca):
    from backend.web_server import app

    res = TestClient(app).get("/api/games/chrono_ark/translate/system-prompt", params={"source_lang": "Chinese", "target_lang": "French"})

    assert res.status_code == 200
    assert res.json() == {"provider": "fake", "source_lang": "Chinese", "system_prompt": "Chinese->French"}
