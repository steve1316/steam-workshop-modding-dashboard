"""Tests for resolving which glossary suggestions an accept request covers."""

from backend.routes.models import SuggestionAction
from backend.translation.suggestions import accepted_suggestions

PENDING = [
    {"english": "Nangao", "source": "南高", "source_lang": "Chinese", "category": "places"},
    {"english": "Miao Ying", "source": "妙影", "category": "characters", "edit_of": "Miaoying"},
    {"source": "无英文"},
]


def test_explicit_terms_pick_only_those_suggestions():
    [a] = accepted_suggestions(PENDING, SuggestionAction(terms=["Nangao", "Missing"]))
    assert (a.suggested, a.english, a.source_lang, a.edit_of) == ("Nangao", "Nangao", "Chinese", None)


def test_all_takes_every_suggestion_with_english_and_applies_renames():
    accepted = accepted_suggestions(PENDING, SuggestionAction(all=True, renames={"Miao Ying": "  Miao Yin  ", "Nangao": " "}))
    assert [(a.suggested, a.english) for a in accepted] == [("Nangao", "Nangao"), ("Miao Ying", "Miao Yin")]
    assert accepted[1].source_lang == "unknown"
    assert accepted[1].edit_of == "Miaoying"
