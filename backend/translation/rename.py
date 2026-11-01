"""Rename a glossary term's English across a mod's translations."""

import re
from collections.abc import Iterable


def replace_whole_term(text: str, old_term: str, new_term: str) -> tuple[str, int]:
    """Replace `old_term` with `new_term` wherever it stands alone in `text`.

    A match must not touch a letter, digit or underscore, so `Nangao` is not replaced inside `Nangaoese`. Unlike a plain `\\b`, this also works
    for terms starting or ending with punctuation, such as `[Lord of Wind] Lidao`.

    Args:
        text: Text to search.
        old_term: Term to replace.
        new_term: Replacement, inserted literally.

    Returns:
        The new text and the replacement count.
    """
    pattern = re.compile(r"(?<!\w)" + re.escape(old_term) + r"(?!\w)")
    return pattern.subn(lambda _match: new_term, text)


def rename_term(rows: Iterable[tuple[str, str, str]], old_english: str, new_english: str, source: str | None = None) -> dict[str, str]:
    """Rename `old_english` to `new_english` as a whole term in each row's translation.

    Args:
        rows: `(key, source text, translation)` triples.
        old_english: English to replace.
        new_english: Replacement English, inserted literally.
        source: Only rows whose source text contains this are renamed, and none when empty. `None` renames every row.

    Returns:
        `{key: renamed translation}` for the rows that changed.
    """
    if old_english == new_english or source == "":
        return {}
    changes: dict[str, str] = {}
    for key, source_text, text in rows:
        if not text or (source is not None and source not in source_text):
            continue
        new_text, count = replace_whole_term(text, old_english, new_english)
        if count:
            changes[key] = new_text
    return changes
