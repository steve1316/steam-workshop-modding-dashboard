"""WH3 workspace: the translations.json overlay and the table rows built from it."""

from backend.games.total_war_warhammer_3.loc.extractor import LocRow
from backend.games.total_war_warhammer_3.translation import workspace
from backend.games.total_war_warhammer_3.translation.drift import DriftRow
from backend.games.total_war_warhammer_3.translation.mods import WH3TranslationMod


def test_overlay_promotes_overrides_blanks_clears_and_marks_disk_text_manual():
    drift = [
        DriftRow("a.loc.tsv", "new", "src", None, "untranslated"),
        DriftRow("a.loc.tsv", "cleared", "src", "On disk", "translated"),
        DriftRow("a.loc.tsv", "kept", "src", "On disk", "translated"),
    ]
    raw = {"new": {"text": "Fresh", "provider": "claude"}, "cleared": {"text": ""}}

    rows = {r.key: (r.translation_text, r.status, r.provider) for r in workspace.overlay_translations(drift, raw)}

    assert rows == {"new": ("Fresh", "translated", "claude"), "cleared": ("", "untranslated", None), "kept": ("On disk", "translated", "manual")}


def test_rows_hide_orphans_that_overlaid_keeps(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace, "extract_parent_strings", lambda mod: {"a.loc.tsv": {"k1": LocRow("k1", "原", True)}})
    monkeypatch.setattr(workspace, "extract_translation_strings", lambda mod: {"a.loc.tsv": {"k1": LocRow("k1", "One", True), "gone": LocRow("gone", "Old", True)}})
    mod = WH3TranslationMod(workshop_id="1", display_name="Test", parent_workshop_ids=("p",), local_source_dir=tmp_path)

    ws = workspace.load_workspace(mod)

    assert {(r.key, r.status) for r in ws.overlaid} == {("k1", "translated"), ("gone", "orphan")}
    assert [r.key for r in ws.rows] == ["k1"]
    assert ws.source_by_key() == {"k1": "原"}
