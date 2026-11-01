"""Tests for the shared translate-preview planner."""

from typing import Any

from backend.translation.planning import plan_batches
from backend.translation.prompt import PromptContext


class _FakeProvider:
    """Records the languages it was asked about and returns canned prompts and estimates."""

    def __init__(self):
        self.prompt_langs: list[str] = []

    def build_prompt(self, entries, source_lang, glossary_prompt, **kwargs):
        self.prompt_langs.append(source_lang)
        return f"system:{source_lang}:{glossary_prompt}", f"user:{','.join(k for k, _ in entries)}"

    def estimate_cost(self, entries, **kwargs):
        return {"strings": len(entries), "target_lang": kwargs["target_lang"]}


def _context(lang: str) -> PromptContext:
    return PromptContext(source_lang=lang, target_lang="Spanish", glossary_prompt=f"G-{lang}")


def test_plan_batches_previews_estimates_and_plans_each_language():
    provider: Any = _FakeProvider()
    chunks = {"Korean": [[("k1", "a"), ("k2", "b")], [("k3", "c")]], "Chinese": [[("c1", "x")]]}

    plan = plan_batches(provider, chunks, _context)

    assert plan["total_batches"] == 3
    assert plan["previews"]["Korean"] == {"system_prompt": "system:Korean:G-Korean", "user_messages": ["user:k1,k2", "user:k3"], "strings_in_language": 3, "batches": 2}
    assert plan["estimates"]["Chinese"] == {"strings": 1, "target_lang": "Spanish"}
    assert plan["batch_plan"] == [
        {"source_lang": "Korean", "keys": ["k1", "k2"], "size": 2},
        {"source_lang": "Korean", "keys": ["k3"], "size": 1},
        {"source_lang": "Chinese", "keys": ["c1"], "size": 1},
    ]


def test_plan_batches_is_empty_for_no_chunks():
    provider: Any = _FakeProvider()
    assert plan_batches(provider, {}, _context) == {"total_batches": 0, "previews": {}, "estimates": {}, "batch_plan": []}
