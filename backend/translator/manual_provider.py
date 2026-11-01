"""
Manual translation provider.

Exports untranslated strings to a JSON file for the user to translate
by hand, then reads the completed translations back in.
"""

import json
from pathlib import Path
from typing import Optional
from backend import config
from backend.translator.base import TranslationProvider
from backend.core.json_store import write_json


class ManualProvider(TranslationProvider):
    """Interactive manual translation provider.

    Exports untranslated strings to a JSON file for the user to fill in
    manually, then reads back the completed translations.

    Attributes:
        _output_dir: Directory where the manual edit JSON file is written.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the manual provider.

        Args:
            output_dir: Directory for manual edit files.
                Defaults to `config.STORAGE_PATH`.
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
        """
        Export strings for manual translation and wait for user input.

        Writes a JSON file with the source text and empty translation
        fields. Prompts the user to fill in translations and press Enter
        to continue.

        Args:
            entries: List of (key, source_text) tuples.
            source_lang: Source language name.
            glossary_prompt: Ignored (user translates manually).
            game_context: Ignored (user translates manually).
            format_rules: Ignored (user translates manually).

        Returns:
            Dictionary mapping key to English translation (from user input).
        """
        # Build the edit file.
        edit_data = {}
        for key, source_text in entries:
            edit_data[key] = {
                "source": source_text,
                "source_lang": source_lang,
                "translation": "",
            }

        # Write the file.
        edit_path = self._output_dir / "manual_edit.json"
        edit_path.parent.mkdir(parents=True, exist_ok=True)

        write_json(edit_path, edit_data)

        print(f"\n{'=' * 60}")
        print(f"MANUAL TRANSLATION MODE")
        print(f"{'=' * 60}")
        print(f"\n  {len(entries)} strings exported for manual translation.")
        print(f"  Source language: {source_lang}")
        print(f"\n  Edit this file:")
        print(f"    {edit_path}")
        print(f'\n  Fill in the "translation" field for each entry.')
        print(f"  Leave blank to skip an entry.")
        print(f"\n{'=' * 60}")

        input("\n  Press Enter when finished editing... ")

        # Read back the completed translations.
        return self._read_completed(edit_path)

    def _read_completed(self, edit_path: Path) -> dict[str, str]:
        """
        Read back completed translations from the manual edit file.

        Args:
            edit_path: Path to the manual edit JSON file.

        Returns:
            Dictionary mapping key to English translation.
        """
        try:
            with open(edit_path, "r", encoding="utf-8") as f:
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
        """
        Estimate the cost of manual translation (always free).

        Args:
            entries: List of (key, source_text) tuples.

        Returns:
            Cost estimation dictionary.
        """
        total_chars = sum(len(text) for _, text in entries)

        return {
            "estimated_cost_usd": 0.0,
            "note": f"Manual translation — no API cost. " f"{len(entries)} strings ({total_chars} chars) to translate.",
        }
