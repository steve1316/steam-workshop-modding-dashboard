"""Tests for the per-mod translation progress tracker."""

from backend.games.chrono_ark import GAME_ID
from backend.models.loc import LocString
from backend.persistence.progress_tracker import ProgressTracker

LANGS = ["Chinese", "Korean"]


def _strings() -> dict[str, LocString]:
    """Two counted strings, one hardcoded DLL string and one blank string."""
    return {
        "Buff/A": LocString(key="Buff/A", type="Text", desc="", translations={"Chinese": "甲"}),
        "Buff/B": LocString(key="Buff/B", type="Text", desc="", translations={"Chinese": "乙"}),
        "DLL/C": LocString(key="DLL/C", type="Text", desc="", translations={"Chinese": "丙"}, untranslatable_reason="Hardcoded in the mod's DLL"),
        "Buff/D": LocString(key="Buff/D", type="Text", desc="", translations={}),
    }


def test_set_translated_ignores_keys_left_out_of_the_total():
    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.update("m", _strings(), LANGS)
    tracker.set_translated("m", ["Buff/A", "Buff/B", "DLL/C", "Buff/D"])

    status = tracker.get_status("m")
    assert status["total"] == 2
    assert status["translated"] == 2
    assert status["untranslated"] == 0
    assert status["percentage"] == 100.0


def test_mark_translated_ignores_keys_left_out_of_the_total():
    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.update("m", _strings(), LANGS)
    tracker.mark_translated("m", ["Buff/A", "DLL/C", "Missing/Key"])

    status = tracker.get_status("m")
    assert status["translated"] == 1
    assert status["untranslated"] == 1
    assert status["percentage"] == 50.0


def test_update_drops_translated_keys_that_became_excluded():
    tracker = ProgressTracker(game_id=GAME_ID)
    strings = _strings()
    strings["DLL/C"].untranslatable_reason = ""
    tracker.update("m", strings, LANGS)
    tracker.set_translated("m", ["Buff/A", "DLL/C"])
    assert tracker.get_status("m")["translated"] == 2

    tracker.update("m", _strings(), LANGS)
    status = tracker.get_status("m")
    assert status["total"] == 2
    assert status["translated"] == 1
