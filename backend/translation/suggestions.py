"""Pick the pending glossary suggestions an accept request covers, with the review modal's renames applied."""

from dataclasses import dataclass

from backend.models.api import SuggestionAction


@dataclass(frozen=True)
class AcceptedSuggestion:
    """One suggestion being accepted into the mod glossary.

    Attributes:
        suggested: English the suggestion was stored under, which is what leaves the pending list.
        english: English to save, which differs from `suggested` when the user edited it.
        edit_of: Existing glossary English this replaces, for edit suggestions.
    """

    suggested: str
    english: str
    source: str
    source_lang: str
    category: str
    edit_of: str | None


def accepted_suggestions(suggestions: list[dict], action: SuggestionAction) -> list[AcceptedSuggestion]:
    """Resolve which pending suggestions `action` accepts.

    Args:
        suggestions: Pending suggestions for the mod.
        action: Explicit `terms` or `all`, plus any edited English in `renames`.

    Returns:
        Accepted suggestions in pending-list order.
    """
    wanted = None if action.all else set(action.terms)
    accepted = []
    for s in suggestions:
        suggested = s.get("english")
        if not suggested or (wanted is not None and suggested not in wanted):
            continue
        english = (action.renames.get(suggested) or "").strip() or suggested
        accepted.append(
            AcceptedSuggestion(
                suggested=suggested,
                english=english,
                source=s.get("source", ""),
                source_lang=s.get("source_lang", "unknown"),
                category=s.get("category", "custom"),
                edit_of=s.get("edit_of") or None,
            )
        )
    return accepted
