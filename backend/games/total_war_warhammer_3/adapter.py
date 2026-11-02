"""Total War: Warhammer III adapter.

Composes the registry, runner, pack and translation routes under `/api/games/total_war_warhammer_3`.
Implements `GameAdapter` and `TranslationCapability` for the Cathay-themed Chinese -> English translation mods.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from backend.games.base import GameAdapter, ModInfo
from backend.games.capabilities.translation import TranslationCapability
from backend.games.total_war_warhammer_3.loc.extractor import (
    normalize_loc_filename,
    read_translation_loc_tsv,
)
from backend.games.total_war_warhammer_3.stores import glossary as glossary_store
from backend.games.total_war_warhammer_3.translation import context as tc
from backend.games.total_war_warhammer_3.translation.mods import (
    WH3_TRANSLATION_MODS,
    get_translation_mod,
)
from backend.models import LocString
from backend.persistence import glossary_manager as gm


class TotalWarWarhammer3Adapter(GameAdapter, TranslationCapability):
    """Total War: Warhammer III game adapter with translation capability."""

    _ROUTER: APIRouter | None = None

    # //////////////////////////////////////////////////////////////////////////////////////////////////
    # //////////////////////////////////////////////////////////////////////////////////////////////////
    # GameAdapter chassis

    @property
    def game_id(self) -> str:
        return "total_war_warhammer_3"

    @property
    def display_name(self) -> str:
        return "Warhammer III"

    @property
    def icon(self) -> str:
        return "total_war_warhammer_3"

    @property
    def capabilities(self) -> list[str]:
        return ["translation"]

    @property
    def router(self) -> APIRouter:
        """Return the composed adapter router, cached at class level.

        Returns:
            Composed `APIRouter`.
        """
        if TotalWarWarhammer3Adapter._ROUTER is None:
            from backend.games.total_war_warhammer_3.routes import build_total_war_warhammer_3_router

            TotalWarWarhammer3Adapter._ROUTER = build_total_war_warhammer_3_router()
        return TotalWarWarhammer3Adapter._ROUTER

    @property
    def settings_schema(self) -> dict[str, dict]:
        return {
            "helper_scripts_path": {"type": "str", "default": ""},
            "rpfm_cli_path": {"type": "str", "default": ""},
            "steam_library_drive": {"type": "str", "default": ""},
        }

    # //////////////////////////////////////////////////////////////////////////////////////////////////
    # //////////////////////////////////////////////////////////////////////////////////////////////////
    # TranslationCapability

    @property
    def target_language(self) -> str:
        return "English"

    @property
    def source_languages(self) -> list[str]:
        return ["Chinese"]

    def get_translation_context(self) -> str:
        return tc.GAME_CONTEXT

    def get_format_preservation_rules(self) -> list[str]:
        return list(tc.FORMAT_PRESERVATION_RULES)

    def get_style_examples(self, source_lang: str = "Chinese") -> dict[str, list[tuple[str, str]]]:
        examples = tc.STYLE_EXAMPLES_BY_LANG.get(source_lang, [])
        return {"unit_descriptions": examples}

    def get_glossary_categories(self) -> dict[str, str | list[str]]:
        return dict(tc.GLOSSARY_CATEGORIES)

    def get_base_glossary_prompt(self, source_lang: str, target_lang: str = "English") -> str:
        """Build the base-game glossary section, filtered to `tc.BASE_GLOSSARY_PROMPT_CATEGORIES`.

        Args:
            source_lang: Source language whose mappings to include.
            target_lang: Language being translated into.

        Returns:
            Glossary section, or an empty string when no terms match.
        """
        return gm.get_glossary_prompt(glossary_store.load_base_glossary(), allowed_categories=tc.BASE_GLOSSARY_PROMPT_CATEGORIES, source_lang=source_lang, target_lang=target_lang)

    @property
    def base_game_path(self) -> Path | None:
        return None

    def extract_base_game_strings(self, game_path: Path | None = None) -> dict[str, LocString]:
        return {}

    def scan_mods(self, search_path: Path | None = None) -> list[ModInfo]:
        """Return the static list of WH3 translation mods from `translation.mods.WH3_TRANSLATION_MODS`.

        Args:
            search_path: Ignored, kept for interface compatibility.

        Returns:
            `ModInfo` list from the static registry.
        """
        return [
            ModInfo(
                mod_id=m.workshop_id,
                name=m.display_name,
                author="",
                path=m.local_source_dir,
                has_loc_files=True,
                has_dll=False,
            )
            for m in WH3_TRANSLATION_MODS
        ]

    def extract_strings(self, mod_path: Path) -> tuple[dict[str, LocString], list[str]]:
        """Read every `.loc.tsv` under `mod_path/text/**`.

        Args:
            mod_path: Local source directory for a translation mod.

        Returns:
            (`{stable_id: LocString}`, warnings), where `stable_id` is `"<normalized_filename>::<loc_key>"`.
        """
        warnings: list[str] = []
        strings: dict[str, LocString] = {}
        text_dir = mod_path / "text"
        if not text_dir.exists():
            warnings.append(f"No text/ directory under {mod_path}")
            return strings, warnings

        for tsv in text_dir.rglob("*.loc.tsv"):
            try:
                rows = read_translation_loc_tsv(tsv)
            except Exception as e:  # noqa: BLE001
                warnings.append(f"Failed to parse {tsv.name}: {e}")
                continue
            norm = normalize_loc_filename(tsv.name)
            for key, row in rows.items():
                stable_id = f"{norm}::{key}"
                strings[stable_id] = LocString(
                    key=key,
                    type="loc",
                    desc="",
                    translations={"English": row.text},
                    source_file=norm,
                )
        return strings, warnings

    def detect_source_language(self, loc_string: LocString) -> str | None:
        return "Chinese"

    def get_untranslated(self, strings: dict[str, LocString], target_lang: str = "English") -> dict[str, LocString]:
        return {sid: s for sid, s in strings.items() if not s.translations.get(target_lang, "").strip()}

    def export_strings(self, output_path: Path, entries: list[LocString]) -> None:
        """Not implemented: export is handled by the pack rebuild + publish workflow."""
        raise NotImplementedError("WH3 translation export uses the existing pack rebuild flow; see backend/games/total_war_warhammer_3/routes/packs.py.")

    def get_mod_url(self, mod_id: str) -> str | None:
        if get_translation_mod(mod_id) is None:
            return None
        return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"

    def get_translation_overrides_dir(self) -> Path | None:
        return None
