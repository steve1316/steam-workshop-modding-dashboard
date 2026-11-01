import json
import time

from backend.data.translation_store import (
    clear_all_translations,
    load_providers,
    load_translations,
    load_translations_raw,
    save_translations_bulk,
    update_single_translation,
)
from backend.games.chrono_ark import GAME_ID


def test_load_returns_empty_when_no_file(tmp_storage):
    result = load_translations("12345", game_id=GAME_ID)
    assert result == {}


def test_save_and_load_round_trip(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello", "key2": "World"}, game_id=GAME_ID)
    result = load_translations("12345", game_id=GAME_ID)
    assert result == {"key1": "Hello", "key2": "World"}


def test_load_backward_compat_flat_format(tmp_storage):
    """Old flat format files should be readable."""
    path = tmp_storage / "mods" / "12345" / "translations.json"
    path.write_text(json.dumps({"key1": "Hello", "key2": "World"}), encoding="utf-8")
    result = load_translations("12345", game_id=GAME_ID)
    assert result == {"key1": "Hello", "key2": "World"}


def test_load_raw_normalizes_flat_entries(tmp_storage):
    """Old flat format entries should be normalized with None timestamps."""
    path = tmp_storage / "mods" / "12345" / "translations.json"
    path.write_text(json.dumps({"key1": "Hello"}), encoding="utf-8")
    raw = load_translations_raw("12345", game_id=GAME_ID)
    assert raw["key1"]["text"] == "Hello"
    assert raw["key1"]["created_at"] is None
    assert raw["key1"]["updated_at"] is None


def test_save_bulk_sets_timestamps_for_new_keys(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello"}, game_id=GAME_ID)
    raw = load_translations_raw("12345", game_id=GAME_ID)
    assert raw["key1"]["created_at"] is not None
    assert raw["key1"]["updated_at"] is not None
    assert raw["key1"]["created_at"] == raw["key1"]["updated_at"]


def test_save_bulk_preserves_created_at_on_update(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello"}, game_id=GAME_ID)
    raw1 = load_translations_raw("12345", game_id=GAME_ID)
    original_created = raw1["key1"]["created_at"]

    time.sleep(0.01)
    save_translations_bulk("12345", {"key1": "Updated"}, game_id=GAME_ID)
    raw2 = load_translations_raw("12345", game_id=GAME_ID)
    assert raw2["key1"]["created_at"] == original_created
    assert raw2["key1"]["updated_at"] > original_created
    assert raw2["key1"]["text"] == "Updated"


def test_save_bulk_skips_unchanged_text(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello"}, game_id=GAME_ID)
    raw1 = load_translations_raw("12345", game_id=GAME_ID)
    original_updated = raw1["key1"]["updated_at"]

    time.sleep(0.01)
    save_translations_bulk("12345", {"key1": "Hello"}, game_id=GAME_ID)
    raw2 = load_translations_raw("12345", game_id=GAME_ID)
    assert raw2["key1"]["updated_at"] == original_updated


def test_update_single_sets_timestamps(tmp_storage):
    update_single_translation("12345", "key1", "Hello", game_id=GAME_ID)
    raw = load_translations_raw("12345", game_id=GAME_ID)
    assert raw["key1"]["text"] == "Hello"
    assert raw["key1"]["created_at"] is not None
    assert raw["key1"]["updated_at"] is not None


def test_update_single_preserves_created_at(tmp_storage):
    update_single_translation("12345", "key1", "Hello", game_id=GAME_ID)
    raw1 = load_translations_raw("12345", game_id=GAME_ID)
    original_created = raw1["key1"]["created_at"]

    time.sleep(0.01)
    update_single_translation("12345", "key1", "Updated", game_id=GAME_ID)
    raw2 = load_translations_raw("12345", game_id=GAME_ID)
    assert raw2["key1"]["created_at"] == original_created
    assert raw2["key1"]["updated_at"] > original_created


def test_clear_all_translations(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello", "key2": "World"}, game_id=GAME_ID)
    clear_all_translations("12345", ["key1", "key2"], game_id=GAME_ID)
    result = load_translations("12345", game_id=GAME_ID)
    assert result["key1"] == ""
    assert result["key2"] == ""


def test_clear_updates_updated_at(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello"}, game_id=GAME_ID)
    raw1 = load_translations_raw("12345", game_id=GAME_ID)
    original_updated = raw1["key1"]["updated_at"]

    time.sleep(0.01)
    clear_all_translations("12345", ["key1"], game_id=GAME_ID)
    raw2 = load_translations_raw("12345", game_id=GAME_ID)
    assert raw2["key1"]["updated_at"] > original_updated


def test_save_bulk_creates_mod_directory(tmp_path):
    save_translations_bulk("99999", {"key1": "Hello"}, game_id=GAME_ID)
    result = load_translations("99999", game_id=GAME_ID)
    assert result == {"key1": "Hello"}


def test_provider_is_recorded_and_kept_when_omitted(tmp_storage):
    save_translations_bulk("12345", {"key1": "Hello", "key2": "World"}, game_id=GAME_ID, provider="claude")
    update_single_translation("12345", "key2", "Earth", game_id=GAME_ID, provider="manual")
    save_translations_bulk("12345", {"key1": "Hi"}, game_id=GAME_ID)
    assert load_providers("12345", game_id=GAME_ID) == {"key1": "claude", "key2": "manual"}
