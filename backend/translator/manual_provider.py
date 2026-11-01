"""Manual provider: exports strings to a JSON file for hand translation, then reads the result back."""

import json
from pathlib import Path

from backend import config
from backend.core.json_store import write_json
from backend.translator.base import TranslationProvider


class ManualProvider(TranslationProvider):
    """Interactive manual translation provider."""

    def __init__(self, output_dir: Path | None = None):
        """Initialize the manual provider.

        Args:
            output_dir: Directory for the edit file, defaulting to `config.STORAGE_PATH`.
        """
        self._output_dir = output_dir or config.STORAGE_PATH

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Manual"

    def translate_batch(
        self,
        entries: list[tuple[str, str]],
        source_lang: str,
        glossary_prompt: str,
        game_context: str = "",
        format_rules: list[str] | None = None,
        style_examples: dict[str, list[tuple[str, str]]] | None = None,
        character_context: dict | None = None,
        target_lang: str = "English",
    ) -> tuple[dict[str, str], list[dict]]:
        """Export strings to a JSON edit file, then block until the user fills in translations and presses Enter.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name.
            glossary_prompt: Ignored.
            game_context: Ignored.
            format_rules: Ignored.

        Returns:
            Key -> English translation from the user's edits, and no suggestions.
        """
        edit_data = {}
        for key, source_text in entries:
            edit_data[key] = {
                "source": source_text,
                "source_lang": source_lang,
                "translation": "",
            }

        edit_path = self._output_dir / "manual_edit.json"
        edit_path.parent.mkdir(parents=True, exist_ok=True)

        write_json(edit_path, edit_data)

        print(f"\n{'=' * 60}")
        print("MANUAL TRANSLATION MODE")
        print(f"{'=' * 60}")
        print(f"\n  {len(entries)} strings exported for manual translation.")
        print(f"  Source language: {source_lang}")
        print("\n  Edit this file:")
        print(f"    {edit_path}")
        print('\n  Fill in the "translation" field for each entry.')
        print("  Leave blank to skip an entry.")
        print(f"\n{'=' * 60}")

        input("\n  Press Enter when finished editing... ")

        return self._read_completed(edit_path), []

    def _read_completed(self, edit_path: Path) -> dict[str, str]:
        """Read back completed translations from the edit file.

        Args:
            edit_path: Edit JSON file.

        Returns:
            Key -> English translation, skipping blanks.
        """
        try:
            with open(edit_path, encoding="utf-8") as f:
                edit_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"  Error reading edit file: {e}")
            return {}

        results = {}
        for key, entry in edit_data.items():
            translation = entry.get("translation", "").strip()
            if translation:
                results[key] = translation

        completed = len(results)
        total = len(edit_data)
        print(f"\n  Read {completed}/{total} translations from edit file.")

        return results

    def estimate_cost(self, entries: list[tuple[str, str]], **kwargs) -> dict:
        """Estimate the cost of manual translation, which is always free.

        Args:
            entries: (key, source_text) tuples.

        Returns:
            Cost estimation dict.
        """
        total_chars = sum(len(text) for _, text in entries)

        return {
            "estimated_cost_usd": 0.0,
            "note": f"Manual translation — no API cost. {len(entries)} strings ({total_chars} chars) to translate.",
        }
