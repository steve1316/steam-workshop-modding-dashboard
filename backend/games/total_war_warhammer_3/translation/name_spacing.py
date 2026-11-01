"""Split joined pinyin names in WH3 translations into one capitalized word per syllable.

Claude tends to run romanized syllables together ("Miaoying") while the game writes names with spaces ("Miao Ying"), so every new translation
passes through `space_pinyin_names` before it is saved.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable

# Runs of Chinese characters in the source text.
_HAN_RUN_RE = re.compile(r"[一-鿿]+")

# A capitalized English word, e.g. "Miaoying" in "[Lord of Raging Gale] Miaoying's".
_WORD_RE = re.compile(r"(?<![A-Za-z])[A-Z][a-z]+(?![A-Za-z])")

# Names are 2 to 4 characters, and single characters are never split.
_MIN_CHARS = 2
_MAX_CHARS = 4

# Cap on readings tried per run so characters with several readings stay cheap.
_MAX_READINGS = 16


def _spaced_forms(source: str) -> dict[str, str]:
    """Map the joined pinyin of every 2 to 4 character run in `source` to its spaced, capitalized form.

    Args:
        source: Source text.

    Returns:
        Joined lowercase pinyin (`miaoying`) to spaced form (`Miao Ying`). Longer runs win when two share a joined form.
    """
    from pypinyin import Style, pinyin

    forms: dict[str, str] = {}
    for run in _HAN_RUN_RE.findall(source):
        for length in range(min(_MAX_CHARS, len(run)), _MIN_CHARS - 1, -1):
            for start in range(len(run) - length + 1):
                readings = pinyin(run[start : start + length], style=Style.NORMAL, heteronym=True)
                for syllables in itertools.islice(itertools.product(*readings), _MAX_READINGS):
                    if all(s.isascii() and s.isalpha() for s in syllables):
                        forms.setdefault("".join(syllables).lower(), " ".join(s.capitalize() for s in syllables))
    return forms


def glossary_words(terms: Iterable[str]) -> frozenset[str]:
    """Collect the lowercase capitalized words of glossary terms, to pass as `keep` to `space_pinyin_names`.

    Args:
        terms: English glossary terms, e.g. "[Dragon General] Fu Yuanshan".

    Returns:
        Lowercase words such as `yuanshan`, so a name the glossary spells joined stays joined.
    """
    return frozenset(word.lower() for term in terms for word in _WORD_RE.findall(term))


def space_pinyin_names(source: str, english: str, keep: frozenset[str] = frozenset()) -> str:
    """Rewrite joined pinyin names in `english` with one capitalized word per syllable.

    Only a capitalized word that is exactly the joined pinyin of characters in this row's `source` changes.
    Ordinary English words, names from other rows,
    non-pinyin spellings and names already spaced or hyphenated are left alone.

    Args:
        source: Chinese source text of the row.
        english: English translation of the row.
        keep: Lowercase words never split, so the mod glossary's spelling wins.

    Returns:
        Translation with joined names split, e.g. "[Lord of Raging Gale] Miao Ying".
    """
    if not source or not english or not _HAN_RUN_RE.search(source):
        return english
    forms = _spaced_forms(source)
    return _WORD_RE.sub(lambda m: m.group(0) if m.group(0).lower() in keep else forms.get(m.group(0).lower(), m.group(0)), english)
