"""Tests for the shared batch streaming and cancel helpers."""

import threading

from backend.translation import streaming


def test_cancel_only_stops_the_matching_games_batch(monkeypatch):
    event = threading.Event()
    monkeypatch.setattr(streaming, "_active", {("chrono_ark", "123"): event})
    assert streaming.cancel_batch("total_war_warhammer_3", "123") is False
    assert not event.is_set()
    assert streaming.cancel_batch("chrono_ark", "123") is True
    assert event.is_set()


def test_cancel_with_nothing_streaming_reports_false():
    assert streaming.cancel_batch("chrono_ark", "nothing-running") is False
