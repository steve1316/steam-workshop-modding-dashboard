"""Tests for the WH3 per-mod glossary store wrappers."""

import json
from pathlib import Path

from backend.games.total_war_warhammer_3.stores.glossary import (
    add_term,
    delete_term,
    load_glossary,
    update_term,
)


def _patch_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)


def test_add_term_persists_entry(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    add_term("abc", {"english": "Cathay Phoenix", "source": "凯薩之凤", "category": "factions"})
    glossary = load_glossary("abc")
    assert "Cathay Phoenix" in glossary
    assert glossary["Cathay Phoenix"]["source"] == "凯薩之凤"
    assert glossary["Cathay Phoenix"]["category"] == "factions"


def test_update_term_rename_removes_old_key(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    add_term("abc", {"english": "Cathay Phoenix", "source": "凯薩之凤", "category": "factions"})
    update_term("abc", "Cathay Phoenix", {"english": "Cathayan Phoenix", "source": "凯薩之凤", "category": "factions"})
    glossary = load_glossary("abc")
    assert "Cathay Phoenix" not in glossary
    assert "Cathayan Phoenix" in glossary


def test_delete_term_removes_entry(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    add_term("abc", {"english": "Phoenix", "source": "凤", "category": "factions"})
    delete_term("abc", "Phoenix")
    assert load_glossary("abc") == {}


def test_load_glossary_returns_empty_when_missing(monkeypatch, tmp_path: Path):
    _patch_root(monkeypatch, tmp_path)
    assert load_glossary("missing-mod") == {}


def test_load_base_glossary_reads_storage(tmp_path, monkeypatch):

    from backend.games.total_war_warhammer_3.stores import glossary as glossary_store

    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    gpath = tmp_path / "games" / "total_war_warhammer_3" / "glossary.json"
    gpath.parent.mkdir(parents=True)
    gpath.write_text(json.dumps({"terms": {"Armour": {"english": "Armour", "category": "stats", "key": "k", "source_mappings": {"Chinese": "护甲"}}}}), encoding="utf-8")

    base = glossary_store.load_base_glossary()
    assert base["terms"]["Armour"]["category"] == "stats"


def test_load_base_glossary_empty_when_missing(tmp_path, monkeypatch):
    from backend.games.total_war_warhammer_3.stores import glossary as glossary_store

    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    assert glossary_store.load_base_glossary() == {"terms": {}}


def test_mod_glossary_as_terms_adapts_flat_format(tmp_path, monkeypatch):
    from backend.games.total_war_warhammer_3.stores import glossary as glossary_store

    monkeypatch.setattr("backend.core.settings.settings.storage_path", tmp_path, raising=True)
    glossary_store.add_term("123", {"english": "Battleguard", "source": "近卫军", "category": "unit_types"})

    adapted = glossary_store.mod_glossary_as_terms("123", "Chinese")
    assert adapted["terms"]["Battleguard"]["category"] == "unit_types"
    assert adapted["terms"]["Battleguard"]["source_mappings"] == {"Chinese": "近卫军"}
