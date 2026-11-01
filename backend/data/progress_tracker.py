"""Tracks which strings are translated and detects added/modified ones by comparing content hashes between scans."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from backend.core.json_store import write_json
from backend.core.paths import mods_path

from ..models import LocString


@dataclass
class ProgressDiff:
    """Result of comparing current strings against a stored snapshot."""

    new_keys: list[str] = field(default_factory=list)
    modified_keys: list[str] = field(default_factory=list)
    removed_keys: list[str] = field(default_factory=list)
    unchanged_keys: list[str] = field(default_factory=list)


class ProgressTracker:
    """Tracks translation progress per mod, storing a snapshot of content hashes for change detection."""

    def __init__(self, storage_path: Path | None = None):
        """Initialize the progress tracker.

        Args:
            storage_path: Storage root override.
        """
        self._storage_path = storage_path

    def _mod_progress_path(self, mod_id: str) -> Path:
        """Get the path to a mod's progress file.

        Args:
            mod_id: Mod's Workshop id.

        Returns:
            The progress JSON path.
        """
        mods_dir = (self._storage_path / "mods") if self._storage_path else mods_path("chrono_ark")
        return mods_dir / mod_id / "progress.json"

    def _load_snapshot(self, mod_id: str) -> dict:
        """Load the stored snapshot for a mod.

        Args:
            mod_id: Mod's Workshop id.

        Returns:
            Snapshot dict, empty if none exists.
        """
        path = self._mod_progress_path(mod_id)
        if not path.exists():
            return {}

        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _save_snapshot(self, mod_id: str, snapshot: dict) -> None:
        """Save a snapshot for a mod.

        Args:
            mod_id: Mod's Workshop id.
            snapshot: Snapshot dict.
        """
        path = self._mod_progress_path(mod_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        write_json(path, snapshot)

    @staticmethod
    def _hash_source_text(loc_string: LocString, source_languages: list[str]) -> str:
        """Hash the source language text of a localization string.

        Args:
            loc_string: String to hash.
            source_languages: Source languages in priority order.

        Returns:
            SHA-256 hex digest.
        """
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
        """Update the progress snapshot and diff it against the previous one.

        Args:
            mod_id: Mod's Workshop id.
            current_strings: Current extracted localization strings.
            source_languages: Source languages for hashing.
            target_lang: Target language name.

        Returns:
            `ProgressDiff` describing what changed.
        """
        old_snapshot = self._load_snapshot(mod_id)
        old_hashes = old_snapshot.get("hashes", {})
        old_translated = set(old_snapshot.get("translated", []))

        langs = source_languages or []

        diff = ProgressDiff()

        new_hashes = {}
        excluded_keys = set()
        for key, loc_str in current_strings.items():
            new_hashes[key] = self._hash_source_text(loc_str, langs)

            # Untranslatable strings (e.g. hardcoded DLL text) don't count.
            if loc_str.untranslatable_reason:
                excluded_keys.add(key)
                continue

            # Strings with only target-language text (English-authored gdata mods) still count. Strings empty in every language are excluded.
            has_source = False
            for lang in langs:
                if lang in loc_str.translations and loc_str.translations[lang].strip():
                    has_source = True
                    break
            if not has_source:
                target_text = loc_str.translations.get(target_lang, "")
                if not target_text.strip():
                    excluded_keys.add(key)

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

        new_snapshot = {
            "hashes": new_hashes,
            "translated": sorted((old_translated & current_keys) - excluded_keys),
            "last_updated": datetime.now(UTC).isoformat(),
            "total_keys": len(current_keys) - len(excluded_keys),
        }
        self._save_snapshot(mod_id, new_snapshot)

        return diff

    def set_translated(self, mod_id: str, keys: list[str]) -> None:
        """Replace the translated key list entirely, unlike `mark_translated` which only adds.

        Args:
            mod_id: Mod's Workshop id.
            keys: Every currently translated key.
        """
        snapshot = self._load_snapshot(mod_id)
        snapshot["translated"] = sorted(keys)
        self._save_snapshot(mod_id, snapshot)

    def mark_translated(self, mod_id: str, keys: list[str]) -> None:
        """Mark keys as translated.

        Args:
            mod_id: Mod's Workshop id.
            keys: Localization keys.
        """
        snapshot = self._load_snapshot(mod_id)
        translated = set(snapshot.get("translated", []))
        translated.update(keys)
        snapshot["translated"] = sorted(translated)
        self._save_snapshot(mod_id, snapshot)

    def unmark_translated(self, mod_id: str, keys: list[str]) -> None:
        """Remove keys from the translated list, e.g. when a translation is cleared.

        Args:
            mod_id: Mod's Workshop id.
            keys: Localization keys.
        """
        snapshot = self._load_snapshot(mod_id)
        translated = set(snapshot.get("translated", []))
        translated -= set(keys)
        snapshot["translated"] = sorted(translated)
        self._save_snapshot(mod_id, snapshot)

    def get_status(self, mod_id: str) -> dict:
        """Get the current translation status for a mod.

        Args:
            mod_id: Mod's Workshop id.

        Returns:
            Total, translated and untranslated counts plus percentage.
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
