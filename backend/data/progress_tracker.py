"""
Progress tracker for monitoring translation status and detecting changes.

Tracks which strings have been translated, detects additions and
modifications by comparing content hashes between scans.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from ..games.storage_paths import mods_path
from ..models import LocString
from backend.core.json_store import write_json


@dataclass
class ProgressDiff:
    """Result of comparing current strings against a stored snapshot.

    Attributes:
        new_keys: Keys that are entirely new (not in previous snapshot).
        modified_keys: Keys whose source text has changed since last snapshot.
        removed_keys: Keys that were in the previous snapshot but are now gone.
        unchanged_keys: Keys that haven't changed since last snapshot.
    """

    new_keys: list[str] = field(default_factory=list)
    modified_keys: list[str] = field(default_factory=list)
    removed_keys: list[str] = field(default_factory=list)
    unchanged_keys: list[str] = field(default_factory=list)


class ProgressTracker:
    """
    Tracks translation progress per mod and detects string changes.

    Stores a snapshot of content hashes for each mod's strings to
    enable change detection between scans.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the progress tracker.

        Args:
            storage_path: Root storage directory.
                Defaults to config.STORAGE_PATH.
        """
        self._storage_path = storage_path

    def _mod_progress_path(self, mod_id: str) -> Path:
        """Get the path to a mod's progress file.

        Args:
            mod_id: The mod's Workshop ID.

        Returns:
            Path to the mod's progress JSON file.
        """
        mods_dir = (self._storage_path / "mods") if self._storage_path else mods_path("chrono_ark")
        return mods_dir / mod_id / "progress.json"

    def _load_snapshot(self, mod_id: str) -> dict:
        """
        Load the stored snapshot for a mod.

        Args:
            mod_id: The mod's Workshop ID.

        Returns:
            Snapshot dictionary, or empty dict if no snapshot exists.
        """
        path = self._mod_progress_path(mod_id)
        if not path.exists():
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _save_snapshot(self, mod_id: str, snapshot: dict) -> None:
        """
        Save a snapshot for a mod.

        Args:
            mod_id: The mod's Workshop ID.
            snapshot: Snapshot dictionary to save.
        """
        path = self._mod_progress_path(mod_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        write_json(path, snapshot)

    @staticmethod
    def _hash_source_text(loc_string: LocString, source_languages: list[str]) -> str:
        """
        Hash the source language text of a localization string.

        Args:
            loc_string: The localization string to hash.
            source_languages: Source languages to check, in priority order.

        Returns:
            SHA-256 hex digest of the source text.
        """
        # Find the first non-empty source language.
        source_lang = None
        for lang in source_languages:
            if lang in loc_string.translations and loc_string.translations[lang]:
                source_lang = lang
                break

        if source_lang:
            text = loc_string.translations.get(source_lang, "")
        else:
            # Fall back to concatenating all non-English translations.
            text = "|".join(loc_string.translations.get(lang, "") for lang in source_languages)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def update(
        self,
        mod_id: str,
        current_strings: dict[str, LocString],
        source_languages: list[str] | None = None,
        target_lang: str = "English",
    ) -> ProgressDiff:
        """
        Update the progress snapshot and compute the diff.

        Compares current strings against the stored snapshot to find
        new, modified, removed, and unchanged keys.

        Args:
            mod_id: The mod's Workshop ID.
            current_strings: Current extracted localization strings.
            source_languages: Source languages for hashing. If None,
                uses all non-English translation keys found.

        Returns:
            `ProgressDiff` describing what changed.
        """
        old_snapshot = self._load_snapshot(mod_id)
        old_hashes = old_snapshot.get("hashes", {})
        old_translated = set(old_snapshot.get("translated", []))

        langs = source_languages or []

        diff = ProgressDiff()

        # Build new hash map and detect empty/untranslatable sources.
        new_hashes = {}
        excluded_keys = set()
        for key, loc_str in current_strings.items():
            new_hashes[key] = self._hash_source_text(loc_str, langs)

            # Untranslatable strings (e.g. hardcoded DLL text) don't count.
            if loc_str.untranslatable_reason:
                excluded_keys.add(key)
                continue

            # If no source language has content, check for strings that
            # only have target-language text (e.g. English-authored gdata
            # mods).  Truly empty strings (no content in any language)
            # are excluded.
            has_source = False
            for lang in langs:
                if lang in loc_str.translations and loc_str.translations[lang].strip():
                    has_source = True
                    break
            if not has_source:
                target_text = loc_str.translations.get(target_lang, "")
                if not target_text.strip():
                    excluded_keys.add(key)

        # Compare.
        current_keys = set(new_hashes.keys())
        previous_keys = set(old_hashes.keys())

        diff.new_keys = sorted(current_keys - previous_keys)
        diff.removed_keys = sorted(previous_keys - current_keys)

        for key in current_keys & previous_keys:
            if new_hashes[key] != old_hashes[key]:
                diff.modified_keys.append(key)
            else:
                diff.unchanged_keys.append(key)

        diff.modified_keys.sort()
        diff.unchanged_keys.sort()

        # Save the updated snapshot.
        new_snapshot = {
            "hashes": new_hashes,
            "translated": sorted((old_translated & current_keys) - excluded_keys),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_keys": len(current_keys) - len(excluded_keys),
        }
        self._save_snapshot(mod_id, new_snapshot)

        return diff

    def set_translated(self, mod_id: str, keys: list[str]) -> None:
        """
        Replace the translated key list entirely.

        Unlike mark_translated (which only adds), this sets the exact list
        so that cleared translations are properly removed.

        Args:
            mod_id: The mod's Workshop ID.
            keys: Complete list of keys that are currently translated.
        """
        snapshot = self._load_snapshot(mod_id)
        snapshot["translated"] = sorted(keys)
        self._save_snapshot(mod_id, snapshot)

    def mark_translated(self, mod_id: str, keys: list[str]) -> None:
        """
        Mark keys as having completed translations.

        Args:
            mod_id: The mod's Workshop ID.
            keys: List of localization keys that have been translated.
        """
        snapshot = self._load_snapshot(mod_id)
        translated = set(snapshot.get("translated", []))
        translated.update(keys)
        snapshot["translated"] = sorted(translated)
        self._save_snapshot(mod_id, snapshot)

    def unmark_translated(self, mod_id: str, keys: list[str]) -> None:
        """
        Remove keys from the translated list (e.g. when a translation is cleared).

        Args:
            mod_id: The mod's Workshop ID.
            keys: List of localization keys to remove from translated.
        """
        snapshot = self._load_snapshot(mod_id)
        translated = set(snapshot.get("translated", []))
        translated -= set(keys)
        snapshot["translated"] = sorted(translated)
        self._save_snapshot(mod_id, snapshot)

    def get_status(self, mod_id: str) -> dict:
        """
        Get the current translation status for a mod.

        Args:
            mod_id: The mod's Workshop ID.

        Returns:
            Dictionary with total, translated, untranslated counts and percentage.
        """
        snapshot = self._load_snapshot(mod_id)
        total = snapshot.get("total_keys", 0)
        translated_set = set(snapshot.get("translated", []))

        translated = len(translated_set)
        untranslated = total - translated
        percentage = (translated / total * 100) if total > 0 else 0.0

        return {
            "mod_id": mod_id,
            "total": total,
            "translated": translated,
            "untranslated": untranslated,
            "percentage": round(percentage, 1),
            "last_updated": snapshot.get("last_updated", "never"),
        }
