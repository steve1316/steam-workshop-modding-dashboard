"""Tests for the WH3 translation prompt rules."""

from backend.games.total_war_warhammer_3.adapter import TotalWarWarhammer3Adapter
from backend.providers.claude_provider import ClaudeProvider


def _title_name_rule(rules: list[str]) -> str:
    """Return the rule that covers titles written before a name, or an empty string.

    Args:
        rules: The adapter's format preservation rules.

    Returns:
        The matching rule text.
    """
    return next((rule for rule in rules if "『" in rule), "")


def test_title_before_name_rule_uses_bracket_title_then_name():
    rule = _title_name_rule(TotalWarWarhammer3Adapter().get_format_preservation_rules())
    assert rule, "WH3 rules should cover a 『title』 written before a name"
    assert "[Sentinel] Sui Tang" in rule
    assert "glossary" in rule.lower()


def test_title_before_name_rule_reaches_the_system_prompt():
    rules = TotalWarWarhammer3Adapter().get_format_preservation_rules()
    system_prompt, _ = ClaudeProvider.__new__(ClaudeProvider).build_prompt([("k1", "『戍望』祟唐")], "Chinese", "", format_rules=rules)
    rule = _title_name_rule(rules)
    assert rule and rule in system_prompt
