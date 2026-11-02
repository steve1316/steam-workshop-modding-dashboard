import json
import time

from backend.games.chrono_ark import GAME_ID
from backend.persistence.character_context import load_character_context, prompt_character_context, save_character_context


def test_load_returns_empty_defaults_when_no_file(tmp_storage):
    result = load_character_context("12345", game_id=GAME_ID)
    assert result == {"source_game": "", "character_name": "", "background": "", "created_at": "", "updated_at": ""}


def test_save_and_load_round_trip(tmp_storage):
    ctx = {"source_game": "Library of Ruina", "character_name": "Roland", "background": "A cynical fixer."}
    save_character_context("12345", ctx, game_id=GAME_ID)
    result = load_character_context("12345", game_id=GAME_ID)
    assert result["source_game"] == "Library of Ruina"
    assert result["character_name"] == "Roland"
    assert result["background"] == "A cynical fixer."
    assert result["created_at"] != ""
    assert result["updated_at"] != ""


def test_save_creates_mod_directory():
    ctx = {"source_game": "Blue Archive", "character_name": "Alice", "background": "A student."}
    save_character_context("99999", ctx, game_id=GAME_ID)
    result = load_character_context("99999", game_id=GAME_ID)
    assert result["source_game"] == "Blue Archive"
    assert result["created_at"] != ""


def test_load_returns_defaults_for_missing_fields(tmp_storage):
    """If the JSON file only has some fields, missing ones default to empty string."""
    path = tmp_storage / "mods" / "12345" / "character_context.json"
    path.write_text(json.dumps({"source_game": "Limbus Company"}), encoding="utf-8")
    result = load_character_context("12345", game_id=GAME_ID)
    assert result == {"source_game": "Limbus Company", "character_name": "", "background": "", "created_at": "", "updated_at": ""}


def test_save_preserves_created_at_on_update(tmp_storage):
    ctx = {"source_game": "Game1", "character_name": "Char1", "background": "Bg1"}
    save_character_context("12345", ctx, game_id=GAME_ID)
    result1 = load_character_context("12345", game_id=GAME_ID)
    original_created = result1["created_at"]

    time.sleep(0.01)
    ctx2 = {"source_game": "Game1", "character_name": "Char2", "background": "Bg2"}
    save_character_context("12345", ctx2, game_id=GAME_ID)
    result2 = load_character_context("12345", game_id=GAME_ID)
    assert result2["created_at"] == original_created
    assert result2["updated_at"] > original_created


def test_prompt_context_is_none_for_a_blank_saved_form(tmp_storage):
    """Saving an empty form sets the timestamps, which alone must not count as context."""
    save_character_context("12345", {"source_game": "", "character_name": " ", "background": ""}, game_id=GAME_ID)
    assert prompt_character_context("12345", game_id=GAME_ID) is None


def test_prompt_context_returns_a_filled_form(tmp_storage):
    save_character_context("12345", {"source_game": "", "character_name": "Roland", "background": ""}, game_id=GAME_ID)
    ctx = prompt_character_context("12345", game_id=GAME_ID)
    assert ctx is not None
    assert ctx["character_name"] == "Roland"
