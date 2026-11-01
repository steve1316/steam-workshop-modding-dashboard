"""Chrono Ark game adapter: CSV/gdata/DLL string extraction and Steam Workshop mod discovery."""

import csv
from pathlib import Path

from fastapi import APIRouter

from backend.core.paths import glossary_path
from backend.core.settings import settings
from backend.data import glossary_manager as gm
from backend.games.base import GameAdapter, ModInfo
from backend.games.capabilities.translation import TranslationCapability
from backend.games.chrono_ark import GAME_ID, csv_extractor, dll_extractor, gdata_extractor, mod_scanner
from backend.models import LocString

# (short_suffix, long_suffix) pairs that may coexist across CSV and gdata sources.
_DESC_SUFFIX_PAIRS = [
    ("_Des", "_Description"),
    ("_Desc", "_Description"),
    ("_PassiveDes", "_PassiveDesc"),
]

# Known key field suffixes, longest first so `_PassiveName` matches before `_Name`.
_KNOWN_SUFFIXES = (
    "_Text_MasterTarget",
    "_CampSelectWord",
    "_PassiveName",
    "_PassiveDesc",
    "_PassiveDes",
    "_Description",
    "_SelectInfo",
    "_Flavor",
    "_Name",
    "_Desc",
    "_Des",
)


def _item_base(key: str) -> str | None:
    """Strip the known field suffix from a localization key to get the item base.

    Args:
        key: Localization key like `SkillExtended/Roland_Rare_Icon_Description`.

    Returns:
        Base without the suffix, or None if no suffix matches.
    """
    for suffix in _KNOWN_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return None


def _drop_cross_source_duplicates(strings: dict[str, LocString]) -> None:
    """Remove duplicate description keys (e.g. `_Des` vs `_Description`), preferring CSV-sourced entries.

    If both come from the same source type, the longer (more canonical) form is kept.

    Args:
        strings: Localization strings, modified in place.
    """
    to_remove: list[str] = []
    for key in list(strings.keys()):
        for short_suffix, long_suffix in _DESC_SUFFIX_PAIRS:
            if key.endswith(short_suffix):
                other_key = key[: -len(short_suffix)] + long_suffix
            elif key.endswith(long_suffix):
                other_key = key[: -len(long_suffix)] + short_suffix
            else:
                continue

            if other_key not in strings or other_key in to_remove:
                break

            this_is_csv = strings[key].source_file.endswith(".csv")
            other_is_csv = strings[other_key].source_file.endswith(".csv")

            if this_is_csv and not other_is_csv:
                to_remove.append(other_key)
            elif other_is_csv and not this_is_csv:
                to_remove.append(key)
            elif key.endswith(short_suffix):
                # Same source type, so prefer the longer form.
                to_remove.append(key)
            else:
                to_remove.append(other_key)
            break

    for key in to_remove:
        strings.pop(key, None)


class ChronoArkAdapter(GameAdapter, TranslationCapability):
    """Game adapter for Chrono Ark.

    `_SOURCE_LANGUAGES` is in detection-priority order and `_SKIP_DLLS` lists dependency DLLs to skip during extraction.
    """

    _CSV_FILES = [
        "LangDataDB.csv",
        "LangDialogueDB.csv",
        "LangRecordsDB.csv",
        "LangSystemDB.csv",
    ]
    # Key prefix to CSV file, following base game conventions.
    _KEY_PREFIX_TO_CSV: dict[str, str] = {
        "Dialogue": "LangDialogueDB.csv",
        "Record": "LangRecordsDB.csv",
        "Battle": "LangSystemDB.csv",
        "CharText": "LangSystemDB.csv",
        "Chartext": "LangSystemDB.csv",
        "Font": "LangSystemDB.csv",
        "Name": "LangSystemDB.csv",
        "Story": "LangSystemDB.csv",
        "StoryGlitch": "LangSystemDB.csv",
        "StoryNames": "LangSystemDB.csv",
        "System": "LangSystemDB.csv",
        "UI": "LangSystemDB.csv",
    }
    _CSV_COLUMNS = [
        "Key",
        "Type",
        "Desc",
        "Korean",
        "English",
        "Japanese",
        "Chinese",
        "Chinese-TW [zh-tw]",
    ]
    _SOURCE_LANGUAGES = ["Chinese", "Korean", "Japanese", "Chinese-TW [zh-tw]"]
    _SKIP_DLLS = {
        "0Harmony.dll",
        "Mono.Cecil.dll",
        "Mono.Cecil.Mdb.dll",
        "Mono.Cecil.Pdb.dll",
        "Mono.Cecil.Rocks.dll",
        "MonoMod.RuntimeDetour.dll",
        "MonoMod.Utils.dll",
    }
    _DLL_MIN_STRING_LENGTH = 4
    _METADATA_FILENAME = "ChronoArkMod.json"
    _GLOSSARY_CATEGORIES = {
        "characters": "Character/",
        "buffs/debuffs": "Buff/",
        "skills": ["Skill/", "SkillExtended/"],
        "items": "Item_Equip/",
        "passives": "Item_Passive/",
    }
    _STYLE_EXAMPLES: dict[str, dict[str, list[tuple[str, str]]]] = {
        "Korean": {
            "skills": [
                ("적 전체에게 &a의 피해를 줍니다. 약화 1을 부여합니다.", "Deal &a damage to all enemies. Apply 1 Weakening."),
                ("아군 한명의 HP를 &a만큼 회복합니다.", "Restore &a HP to an ally."),
                ("적 하나에게 &a의 피해를 줍니다. 이 스킬은 방어력을 무시합니다.", "Deal &a damage to an enemy. This skill ignores Defense."),
            ],
            "buffs/debuffs": [
                ("다음 공격에 의한 받는 피해가 30% 증가합니다.", "Damage taken from the next attack is increased by 30%."),
                ("매 턴 시작 시 HP를 &a만큼 회복합니다.", "Restore &a HP at the start of each turn."),
                ("공격력이 &a만큼 증가합니다.", "Attack is increased by &a."),
            ],
            "items": [
                ("공격 시 100%를 초과하는 명중률은 치명타 확률로 변환됩니다.", "When attacking, any Accuracy exceeding 100% is converted into Critical Chance."),
                ("전투 시작 시 모든 아군의 방어력이 &a 증가합니다.", "At the start of battle, all allies gain &a Defense."),
            ],
        },
        "Chinese": {
            "skills": [
                ("对所有敌人造成&a点伤害。施加1层弱化。", "Deal &a damage to all enemies. Apply 1 Weakening."),
                ("恢复一名友军&a点HP。", "Restore &a HP to an ally."),
                ("对一名敌人造成&a点伤害。此技能无视防御力。", "Deal &a damage to an enemy. This skill ignores Defense."),
            ],
            "buffs/debuffs": [
                ("下次攻击受到的伤害增加30%。", "Damage taken from the next attack is increased by 30%."),
                ("每回合开始时恢复&a点HP。", "Restore &a HP at the start of each turn."),
                ("攻击力增加&a。", "Attack is increased by &a."),
            ],
            "items": [
                ("攻击时超过100%的命中率将转化为暴击率。", "When attacking, any Accuracy exceeding 100% is converted into Critical Chance."),
                ("战斗开始时所有友军防御力增加&a。", "At the start of battle, all allies gain &a Defense."),
            ],
        },
        "Japanese": {
            "skills": [
                ("敵全体に&aのダメージを与えます。弱体化を1付与します。", "Deal &a damage to all enemies. Apply 1 Weakening."),
                ("味方1人のHPを&a回復します。", "Restore &a HP to an ally."),
                ("敵1体に&aのダメージを与えます。このスキルは防御力を無視します。", "Deal &a damage to an enemy. This skill ignores Defense."),
            ],
            "buffs/debuffs": [
                ("次の攻撃による被ダメージが30%増加します。", "Damage taken from the next attack is increased by 30%."),
                ("毎ターン開始時にHPを&a回復します。", "Restore &a HP at the start of each turn."),
                ("攻撃力が&a増加します。", "Attack is increased by &a."),
            ],
            "items": [
                ("攻撃時、100%を超える命中率はクリティカル率に変換されます。", "When attacking, any Accuracy exceeding 100% is converted into Critical Chance."),
                ("戦闘開始時、全味方の防御力が&a増加します。", "At the start of battle, all allies gain &a Defense."),
            ],
        },
    }

    @staticmethod
    def csv_for_key(key: str) -> str:
        """Return the canonical CSV filename for a localization key's prefix."""
        prefix = key.split("/", 1)[0] if "/" in key else ""
        csv = ChronoArkAdapter._KEY_PREFIX_TO_CSV.get(prefix)
        if csv:
            return csv
        # Only these prefixes go to LangDataDB. Slashless custom mod keys and unknown prefixes fall back to LangSystemDB.
        _DATA_PREFIXES = {
            "ArkUpgrade",
            "Buff",
            "Character",
            "DLL",
            "Character_Skin",
            "CurseList",
            "EnchantList",
            "Enemy",
            "Item_Active",
            "Item_Consume",
            "Item_Equip",
            "Item_Friendship",
            "Item_Misc",
            "Item_Passive",
            "Item_Potions",
            "Item_Scroll",
            "RandomEvent",
            "SimpleCampDialogue",
            "Skill",
            "SkillExtended",
            "SkillKeyword",
            "SpecialKey",
            "SpecialRule",
            "UnlockWindow",
        }
        if prefix in _DATA_PREFIXES:
            return "LangDataDB.csv"
        return "LangSystemDB.csv"

    def get_translation_overrides_dir(self) -> Path | None:
        """Return the ModTranslationInjector mod directory, derived from `settings.base_game_path` (`ChronoArk_Data/StreamingAssets`).

        Returns:
            Mod directory, or None if it does not exist.
        """
        game_root = settings.base_game_path.parent.parent
        overrides_dir = game_root / "Mod" / "ModTranslationInjector"
        if not overrides_dir.exists():
            return None
        return overrides_dir

    @property
    def base_game_path(self) -> Path | None:
        return settings.base_game_path

    @property
    def workshop_path(self) -> Path:
        return settings.workshop_path

    @property
    def game_id(self) -> str:
        return GAME_ID

    @property
    def game_name(self) -> str:
        return "Chrono Ark"

    @property
    def display_name(self) -> str:
        return "Chrono Ark"

    @property
    def icon(self) -> str:
        return "chrono_ark"

    @property
    def capabilities(self) -> list[str]:
        return ["translation"]

    _ROUTER: APIRouter | None = None

    @property
    def router(self) -> APIRouter:
        """Return the composed Chrono Ark router, cached at class level so it survives `set_active_game` rebinds."""
        if ChronoArkAdapter._ROUTER is None:
            from backend.games.chrono_ark.routes import build_chrono_ark_router

            ChronoArkAdapter._ROUTER = build_chrono_ark_router()
        return ChronoArkAdapter._ROUTER

    @property
    def target_language(self) -> str:
        return "English"

    @property
    def source_languages(self) -> list[str]:
        return self._SOURCE_LANGUAGES

    def get_translation_context(self) -> str:
        return '"Chrono Ark", a roguelike deck-building RPG'

    def get_format_preservation_rules(self) -> list[str]:
        return [
            'Preserve ALL formatting tags exactly as-is: `<b>`, `</b>`, `<color=#XXXXXX>`, `</color>`, `<sprite=N>`, `<sprite name="...">`. Do NOT translate or modify these tags.',
            "Preserve ALL placeholder variables exactly as-is: `&a`, `&b`, `&c`, `%`. These are runtime value substitutions.",
            "Match the tone and style of the base game: The game uses a fantasy/adventure tone with concise, punchy skill descriptions. Character dialogue is conversational.",
            "Use consistent terminology: Always use the exact English terms from the glossary below. Do NOT paraphrase or use synonyms for glossary terms.",
            "Keep translations concise: Skill and buff descriptions should be brief and clear. Avoid overly formal or wordy translations.",
            "Preserve line breaks: Source text uses literal `\\n` to represent line breaks. Keep every `\\n` in the translated output in the same positions. Do NOT remove or merge lines.",
            "End sentences with periods: Even if the original source text does not end sentences with punctuation, always add a period at the end of each English sentence or description line. Exception: single-word names or titles should NOT have periods.",
            "Use double quotes: When quoting text, always use double quotes (`\"`) instead of single quotes (`'`). For example: \"Dual Wield\" not 'Dual Wield'.",
        ]

    def get_style_examples(self, source_lang: str = "Korean") -> dict[str, list[tuple[str, str]]]:
        examples = self._STYLE_EXAMPLES.get(source_lang)
        if examples is None:
            examples = self._STYLE_EXAMPLES["Korean"]
        return examples

    def scan_mods(self, search_path: Path | None = None) -> list[ModInfo]:
        """Discover installed workshop mods by their `ChronoArkMod.json` files.

        Args:
            search_path: Workshop directory override (defaults to `settings.workshop_path`).

        Returns:
            `ModInfo` per mod, sorted by mod_id.
        """
        workshop_path = search_path or settings.workshop_path
        return mod_scanner.scan_workshop(
            workshop_path=workshop_path,
            metadata_filename=self._METADATA_FILENAME,
            skip_dlls=self._SKIP_DLLS,
            ignored_ids=set(settings.ignored_mods),
        )

    def find_mod(self, mod_id: str, search_path: Path | None = None) -> ModInfo | None:
        """Find one installed workshop mod by id.

        Args:
            mod_id: Mod's Workshop id.
            search_path: Workshop directory override (defaults to `settings.workshop_path`).

        Returns:
            The mod's `ModInfo`, or `None` when it is not installed or is ignored.
        """
        return mod_scanner.find_workshop_mod(
            workshop_path=search_path or settings.workshop_path,
            mod_id=mod_id,
            metadata_filename=self._METADATA_FILENAME,
            skip_dlls=self._SKIP_DLLS,
            ignored_ids=set(settings.ignored_mods),
        )

    def extract_strings(self, mod_path: Path) -> tuple[dict[str, LocString], list[str]]:
        """Extract localization strings from CSVs, then merge in gdata JSON (`gdata/Add/`) and DLL strings not already covered.

        Args:
            mod_path: Mod root directory.

        Returns:
            `({key: LocString}, variant/duplicate file relative paths)`.
        """
        strings, variants = csv_extractor.extract_mod_strings(mod_path)

        gdata_strings = gdata_extractor.extract_mod_gdata_strings(mod_path)

        # A JSON key duplicates a CSV key if equal (case-insensitive) or if the CSV has a prefixed form like
        # "Character/xxx_Text_Battle_Cri_0" for JSON "Text_Battle_Cri_0".
        csv_keys_lower: set[str] = set()
        csv_suffixes_lower: set[str] = set()
        # Item base to source texts, to catch CSV `_Name` vs JSON `_Description` with identical text.
        csv_base_texts: dict[str, set[str]] = {}
        for csv_key, csv_loc in strings.items():
            csv_keys_lower.add(csv_key.lower())
            if "/" in csv_key:
                csv_suffixes_lower.add(csv_key.split("/", 1)[1].lower())
            base = _item_base(csv_key)
            if base is not None:
                texts = csv_base_texts.setdefault(base, set())
                texts.update(v for v in csv_loc.translations.values() if v)

        for key, loc_str in gdata_strings.items():
            if key in strings or key.lower() in csv_keys_lower:
                continue
            # The `_` boundary avoids false suffix matches.
            needle = "_" + key.lower()
            if any(suffix.endswith(needle) for suffix in csv_suffixes_lower):
                continue
            base = _item_base(key)
            if base is not None:
                csv_texts = csv_base_texts.get(base)
                if csv_texts and any(v in csv_texts for v in loc_str.translations.values() if v):
                    continue
            strings[key] = loc_str

        dll_strings = dll_extractor.extract_mod_dll_loc_strings(
            mod_path,
            self._SKIP_DLLS,
        )
        for key, loc_str in dll_strings.items():
            if key not in strings:
                strings[key] = loc_str

        # Orphan CJK strings in DLLs have no localization key (e.g. `this.PassiveDes = "中文"`).
        orphan_strings = dll_extractor.extract_mod_dll_orphan_strings(
            mod_path,
            self._SKIP_DLLS,
            dll_strings,
            self._DLL_MIN_STRING_LENGTH,
        )
        existing_values: set[str] = set()
        for loc_str in strings.values():
            for val in loc_str.translations.values():
                if val:
                    existing_values.add(val)
        for key, loc_str in orphan_strings.items():
            chinese = loc_str.translations.get("Chinese", "")
            if chinese in existing_values:
                continue
            if key not in strings:
                strings[key] = loc_str

        _drop_cross_source_duplicates(strings)
        return strings, variants

    def extract_base_game_strings(self, game_path: Path | None = None) -> dict[str, LocString]:
        """Parse the base game's `Lang*.csv` files for glossary building.

        Args:
            game_path: StreamingAssets override (defaults to `settings.base_game_path`).

        Returns:
            `{key: LocString}`.
        """
        path = game_path or settings.base_game_path
        return csv_extractor.extract_base_game_strings(path, self._CSV_FILES)

    def detect_source_language(self, loc_string: LocString) -> str | None:
        """Return the first source language (in `_SOURCE_LANGUAGES` order) with non-empty text.

        Args:
            loc_string: String to inspect.

        Returns:
            Language name, or None.
        """
        return csv_extractor.detect_source_language(loc_string, self._SOURCE_LANGUAGES)

    def get_untranslated(self, strings: dict[str, LocString]) -> dict[str, LocString]:
        """Keep entries with an empty English column but some source-language text.

        Args:
            strings: All localization strings.

        Returns:
            Only the strings needing translation.
        """
        return csv_extractor.get_untranslated_strings(strings, self._SOURCE_LANGUAGES)

    def get_glossary_categories(self) -> dict[str, str | list[str]]:
        """Return glossary category to key-prefix mappings.

        Returns:
            E.g. `{"characters": "Character/", "skills": ["Skill/", "SkillExtended/"]}`.
        """
        return self._GLOSSARY_CATEGORIES

    def get_base_glossary_prompt(self, source_lang: str, target_lang: str = "English") -> str:
        """Build the base-game glossary section, filtered to `settings.glossary_categories`.

        Args:
            source_lang: Source language to include (e.g. `"Chinese"`).
            target_lang: Language translated into.

        Returns:
            Glossary section, or `""` when no terms match.
        """
        return gm.get_glossary_prompt(gm.load_glossary(glossary_path(GAME_ID)), allowed_categories=settings.glossary_categories, source_lang=source_lang, target_lang=target_lang)

    def export_strings(self, output_path: Path, entries: list[LocString]) -> None:
        """Write entries to a Chrono Ark CSV (Key, Type, Desc, then language columns).

        Args:
            output_path: Destination CSV.
            entries: Strings to write.
        """
        columns = self._CSV_COLUMNS
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for entry in entries:
                row = [entry.key, entry.type, entry.desc]
                for lang in columns[3:]:
                    row.append(entry.translations.get(lang, ""))
                writer.writerow(row)

    def get_mod_url(self, mod_id: str) -> str | None:
        """Return the Steam Workshop URL for a mod.

        Args:
            mod_id: Workshop item id.

        Returns:
            Workshop URL.
        """
        return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"

    def export_gdata_strings(self, mod_path: Path, translations: dict[str, str]) -> list[str]:
        """Write translations back into a mod's gdata JSON files.

        Args:
            mod_path: Mod root directory.
            translations: `{key: English text}`.

        Returns:
            Modified JSON filenames.
        """
        return gdata_extractor.export_gdata_translations(mod_path, translations)
