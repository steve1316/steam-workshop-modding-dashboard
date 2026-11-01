"""WH3-specific text injected into LLM translation prompts.

Consumed by `TotalWarWarhammer3Adapter` through the `TranslationCapability` methods.
"""

from __future__ import annotations

GAME_CONTEXT = (
    "Total War: Warhammer III - community mods for the strategy game. "
    "Translate Chinese game text into natural English. Preserve official WH3 "
    "terminology (Lord, Hero, Unit, Faction names like Cathay/Empire/Greenskins, "
    "lores of magic, etc.). Many translations cover unit names, ability descriptions, "
    "lord backgrounds, and faction lore for fan-made Cathay-themed mods."
)

FORMAT_PRESERVATION_RULES: list[str] = [
    "Preserve all `[[col:...]]...[[/col]]` color tags verbatim, including the closing tag.",
    "Preserve `[[img:...]]` image tokens verbatim.",
    "Preserve substitution tokens of the form `%N%`, `{0}`, `{{...}}`, and `<<...>>` verbatim.",
    "Preserve literal `\\n` line breaks; do not insert or remove them.",
    "Preserve leading/trailing whitespace exactly as it appears in the source string.",
    "Do not translate game-internal keys or identifiers that appear in the text.",
    "Render a 『title』 written before a character name as `[Title] Name` (e.g. 『戍望』祟唐 -> `[Sentinel] Sui Tang`), both in translated text "
    "and in suggested glossary terms. Do not use `Name / 'Title'` or `the 'Title,' Name`.",
    "Romanize Chinese names of characters, creatures and places in pinyin with each syllable as its own capitalized word, as the official game "
    "does (Miao Ying, Yuan Bo): 妙影 -> `Miao Ying`, 昭明 -> `Zhao Ming`, 烛龙 -> `Zhu Long`, 『狂飙烈风之主』妙影 -> `[Lord of Raging Gale] Miao Ying`. "
    "Never join the syllables (`Miaoying`). Use the same form in suggested glossary terms.",
]

STYLE_EXAMPLES_BY_LANG: dict[str, list[tuple[str, str]]] = {
    "Chinese": [
        ("[[col:yellow]]近卫军[[/col]]", "[[col:yellow]]Battleguard[[/col]]"),
        ("一支由凯薩之鸟召唤的精锐部队。", "An elite force summoned by the Cathayan Phoenix."),
        ("它们用毒匕攻击敌人, 拥有出色的护甲。", "They attack enemies with venomous daggers and have excellent armor."),
        # Recruitment unlocks read "Unlocks recruitment for ...".
        (
            "获得『卫土戍卒(斩马剑)』『卫土戍卒(重型连弩)』招募许可",
            "Unlocks recruitment for Frontier Guards (Zhan Ma Sword) and Frontier Guards (Heavy Repeater).",
        ),
    ],
}

GLOSSARY_CATEGORIES: dict[str, str | list[str]] = {
    "factions": "Faction names (e.g. Cathay, Empire, Greenskins, Khorne).",
    "lords_heroes": "Named legendary lords and heroes (e.g. Miao Ying, Zhao Ming).",
    "unit_types": "Unit category names (Battleguard, Dragon Guard, Crane Gunner).",
    "abilities": "Ability and spell names (Wind of Death, Phoenix Roar).",
    "lore_terms": "Lore/setting-specific terms (Wu-Xing Compass, Great Bastion).",
    "technologies": "Technology and rite names.",
    "items": "Item, weapon, and armor names.",
}

# Base-glossary categories injected into the translation prompt. `regions` is excluded because its ~900 proper nouns would bloat every prompt.
# They stay in the glossary file and the Glossary page.
BASE_GLOSSARY_PROMPT_CATEGORIES: list[str] = ["stats", "attributes", "ui_terms"]
