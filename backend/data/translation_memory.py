"""
Translation memory for caching and reusing past translations.

Stores source→English translations keyed by content hash to avoid
redundant API calls and reduce cost.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend.games.storage_paths import translation_memory_path
from backend.core.json_store import write_json


class TranslationMemory:
    """
    Persistent cache of source text → English translations.

    Translations are keyed by SHA-256 hash of the source text for
    efficient lookup regardless of which mod the text came from.
    """

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize the translation memory.

        Args:
            path: Path to the JSON storage file.
                Defaults to storage/translation_memory.json.
        """
        if path is None:
            path = translation_memory_path("chrono_ark")
        self._path = path
        self._entries: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
        self._load()

    def _load(self) -> None:
        """Load translation memory from disk."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._entries = {}

    def save(self) -> None:
        """Persist translation memory to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self._path, self._entries)

    @staticmethod
    def _hash(text: str) -> str:
        """
        Compute SHA-256 hash of the source text.

        Args:
            text: Source text to hash.

        Returns:
            Hex digest of the hash.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def lookup(self, source_text: str) -> Optional[str]:
        """
        Look up a cached translation for the given source text.

        Args:
            source_text: The original (non-English) text.

        Returns:
            The cached English translation, or None if not found.
        """
        key = self._hash(source_text)
        entry = self._entries.get(key)
        if entry:
            self._hits += 1
            return entry["translation"]
        self._misses += 1
        return None

    def store(
        self,
        source_text: str,
        translation: str,
        source_lang: str = "",
    ) -> None:
        """
        Store a new translation in the memory.

        Args:
            source_text: The original (non-English) text.
            translation: The English translation.
            source_lang: The source language name.
        """
        key = self._hash(source_text)
        self._entries[key] = {
            "source": source_text,
            "translation": translation,
            "source_lang": source_lang,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_stats(self) -> dict:
        """
        Get translation memory statistics.

        Returns:
            Dictionary with total entries, session hits/misses, and hit rate.
        """
        total_lookups = self._hits + self._misses
        hit_rate = (self._hits / total_lookups * 100) if total_lookups > 0 else 0.0

        return {
            "total_entries": len(self._entries),
            "session_hits": self._hits,
            "session_misses": self._misses,
            "hit_rate_percent": round(hit_rate, 1),
        }
