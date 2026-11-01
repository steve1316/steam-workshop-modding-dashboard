"""The CLI manual provider returns the same shape as every other provider."""

import json
from pathlib import Path

from backend.translator.manual_provider import ManualProvider


def test_translate_batch_returns_translations_and_no_suggestions(tmp_path: Path, monkeypatch):
    def fill_in(_prompt: str) -> str:
        path = tmp_path / "manual_edit.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["A_name"]["translation"] = "Reminiscence"
        path.write_text(json.dumps(data), encoding="utf-8")
        return ""

    monkeypatch.setattr("builtins.input", fill_in)
    translations, suggestions = ManualProvider(output_dir=tmp_path).translate_batch([("A_name", "追憶"), ("B_name", "うさぎ")], "Japanese", "")
    assert translations == {"A_name": "Reminiscence"}
    assert suggestions == []
