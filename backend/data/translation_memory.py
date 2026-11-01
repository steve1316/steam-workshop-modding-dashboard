"""Translation memory: source -> English translations keyed by content hash, to avoid redundant API calls."""

import hashlib
import json
from datetime import UTC, datetime

from backend.core.json_store import write_json
from backend.core.paths import translation_memory_path


class TranslationMemory:
    """Persistent cache of source text -> English translations, keyed by SHA-256 of the source so lookups work across mods."""

    def __init__(self, *, game_id: str):
        """Initialize the translation memory.

        Args:
            game_id: Game whose memory file to use.
        """
        self._path = translation_memory_path(game_id)
        self._entries: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
        self._load()

    def _load(self) -> None:
        """Load translation memory from disk."""
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._entries = {}

    def save(self) -> None:
        """Persist translation memory to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self._path, self._entries)

    @staticmethod
    def _hash(text: str) -> str:
        """Compute the SHA-256 hex digest of the source text.

        Args:
            text: Source text.

        Returns:
            Hex digest.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def lookup(self, source_text: str) -> str | None:
        """Look up a cached translation for the source text.

        Args:
            source_text: Original non-English text.

        Returns:
            Cached English translation, or None.
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
        """Store a translation in the memory.

        Args:
            source_text: Original non-English text.
            translation: English translation.
            source_lang: Source language name.
        """
        key = self._hash(source_text)
        self._entries[key] = {
            "source": source_text,
            "translation": translation,
            "source_lang": source_lang,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_stats(self) -> dict:
        """Get translation memory statistics.

        Returns:
            Total entries, session hits/misses and hit rate.
        """
        total_lookups = self._hits + self._misses
        hit_rate = (self._hits / total_lookups * 100) if total_lookups > 0 else 0.0

        return {
            "total_entries": len(self._entries),
            "session_hits": self._hits,
            "session_misses": self._misses,
            "hit_rate_percent": round(hit_rate, 1),
        }
