"""Registry of WH3 translation mods the user maintains.

Each entry pairs a published translation Workshop id with the parent mod(s) whose `.loc` strings it covers and the local dir of loose `.loc.tsv` files.
`Cathay Dragons Battle in the Field` is omitted until a local source dir is confirmed for parent id `3061752415`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.settings import settings


@dataclass(frozen=True)
class WH3TranslationMod:
    """One translation mod entry.

    Attributes:
        workshop_id: Workshop id of the published translation mod.
        display_name: Name shown in the dashboard.
        parent_workshop_ids: Parent mod ids whose strings this covers, several for collection translations (e.g. Deer24).
        local_source_dir: Absolute path to the loose `.loc.tsv` files the user edits.
        source_language: Parent text language, currently always `"Chinese"`.
        target_language: Target language, currently always `"English"`.
        prefix: Load-order prefix for new `.loc.tsv` files in `<local_source_dir>/text/`.
    """

    workshop_id: str
    display_name: str
    parent_workshop_ids: tuple[str, ...]
    local_source_dir: Path
    source_language: str = "Chinese"
    target_language: str = "English"
    prefix: str = "@@"


def translation_mods() -> tuple[WH3TranslationMod, ...]:
    """Return the registered translation mods, with source dirs under `settings.tw3.translation_mods_path`.

    Returns:
        The mods, or none while that folder is unset so nothing reads or writes a relative path.
    """
    if not settings.tw3.translation_mods_path.strip():
        return ()
    root = Path(settings.tw3.translation_mods_path)
    return (
        WH3TranslationMod(
            workshop_id="3315737452",
            display_name="Zerooz Cathy Alternative English Translation",
            parent_workshop_ids=("2901237965",),
            local_source_dir=root / "Zerooz_English_Translation_corrections",
        ),
        WH3TranslationMod(
            workshop_id="3317696617",
            display_name="Dragon General Fu Yuanshan Reforged Alternative English Translation",
            parent_workshop_ids=("3316985957",),
            local_source_dir=root / "zzz_cth_fuyuanshan_faction_Alternative_English_Translation",
            prefix="!!!",
        ),
        WH3TranslationMod(
            workshop_id="3392058226",
            display_name="Whc's Cathay unit pack - War under Heaven Alternative English Translation",
            parent_workshop_ids=("3297754796",),
            local_source_dir=root / "zzz_@whc_cth_unit_wuh_Alternative_English_Translation",
        ),
        WH3TranslationMod(
            workshop_id="3393724674",
            display_name="Deer24 Alternative English Translation Collection",
            parent_workshop_ids=(
                "2789903784",
                "2804084630",
                "2908711955",
                "2859396310",
                "2872222879",
            ),
            local_source_dir=root / "zzz_DEER24_Alternative_English_Translation",
        ),
        WH3TranslationMod(
            workshop_id="3393724734",
            display_name="Great Harmony Sentinel Alternative English Translation",
            parent_workshop_ids=("3442971928",),
            local_source_dir=root / "zzz_Great_Harmony_Sentinel_Alternative_English_Translation",
        ),
    )


def get_translation_mod(workshop_id: str) -> WH3TranslationMod | None:
    """Look up a translation mod by its Workshop id.

    Args:
        workshop_id: Workshop id of the translation mod.

    Returns:
        The matching mod, or `None` if not registered.
    """
    for mod in translation_mods():
        if mod.workshop_id == workshop_id:
            return mod
    return None
