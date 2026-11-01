"""Shared domain models used across extractors, translators, and the web UI."""

from dataclasses import dataclass, field


@dataclass
class LocString:
    """A single localization entry with all language columns.

    Attributes:
        key: Localization key (e.g., `"Buff/B_Armor_P_1_Name"`).
        translations: Language name to text, e.g. `{"Korean": "...", "English": "..."}`.
        untranslatable_reason: If non-empty, a user-facing reason the CSV pipeline cannot translate this string.
    """

    key: str
    type: str
    desc: str
    translations: dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    untranslatable_reason: str = ""
