"""Tests for TranslationCapability.get_base_glossary_prompt across game adapters.

Regression: the Settings "Load Prompt" preview used to inject the Chrono Ark base
glossary regardless of the active game, so Chrono Ark character terms (Azar, Charon)
leaked into the WH3 system prompt. Each adapter must build its base-glossary section
from its own glossary file and its own prompt categories.
"""

from backend.core.settings import settings
from backend.games.chrono_ark import adapter as ca_adapter
from backend.games.total_war_warhammer_3 import adapter as wh3_adapter
from backend.games.total_war_warhammer_3.stores import glossary as glossary_store
from backend.persistence import glossary_manager as gm


def _glossary(terms: dict) -> dict:
    return {"terms": terms}


def test_chrono_ark_base_glossary_prompt_uses_chrono_ark_categories(monkeypatch):
    """Chrono Ark builds its prompt from the Chrono Ark glossary, filtered to settings.glossary_categories."""
    fake = _glossary(
        {
            "Character/Azar_name": {"english": "Azar", "category": "characters", "source_mappings": {"Chinese": "阿扎尔"}},
            "Region/Foo": {"english": "Foo Region", "category": "regions", "source_mappings": {"Chinese": "某地"}},
        }
    )
    monkeypatch.setattr(gm, "load_glossary", lambda *a, **k: fake)
    monkeypatch.setattr(settings, "glossary_categories", ["characters", "mechanics"])

    prompt = ca_adapter.ChronoArkAdapter().get_base_glossary_prompt("Chinese")

    assert "Azar" in prompt
    assert "Foo Region" not in prompt  # regions is not an allowed prompt category


def test_wh3_base_glossary_prompt_excludes_chrono_ark_character_terms(monkeypatch):
    """WH3 builds its prompt from the WH3 base glossary, filtered to BASE_GLOSSARY_PROMPT_CATEGORIES.

    A Chrono-Ark-style `characters` term must never appear in the WH3 prompt.
    """
    fake = _glossary(
        {
            "stat/armor": {"english": "Armor", "category": "stats", "source_mappings": {"Chinese": "防御力"}},
            "Character/Azar_name": {"english": "Azar", "category": "characters", "source_mappings": {"Chinese": "阿扎尔"}},
        }
    )
    monkeypatch.setattr(glossary_store, "load_base_glossary", lambda *a, **k: fake)

    prompt = wh3_adapter.TotalWarWarhammer3Adapter().get_base_glossary_prompt("Chinese")

    assert "Armor" in prompt
    assert "Azar" not in prompt
