"""
Steam Workshop Modding Dashboard - CLI entry point for extracting, translating, and managing mod localization strings.

Usage:
    python -m backend.cli extract --base-game
    python -m backend.cli extract --mod <id>
    python -m backend.cli extract --all-mods
    python -m backend.cli translate --mod <id> [--provider claude|openai|deepl]
    python -m backend.cli translate --mod <id> --dry-run
    python -m backend.cli status [--mod <id>]
    python -m backend.cli glossary --show|--build|--add <source> <english>
    python -m backend.cli export --mod <id>
"""

import argparse
import sys
from pathlib import Path

from backend.core.errors import DomainError
from backend.core.paths import GameStorage, glossary_path
from backend.core.settings import settings
from backend.games.chrono_ark import GAME_ID
from backend.games.chrono_ark.adapter import ChronoArkAdapter
from backend.games.chrono_ark.services.mods import export_mod, extract_mod, save_extracted_strings
from backend.games.chrono_ark.services.translation import load_mod_strings, persist_batch, prompt_context
from backend.games.registry import get_adapter, list_games
from backend.persistence.glossary_manager import (
    add_glossary_term,
    build_glossary_from_base_game,
    load_glossary,
    print_glossary,
    save_glossary,
)
from backend.persistence.progress_tracker import ProgressTracker
from backend.persistence.translation_memory import TranslationMemory
from backend.persistence.translation_store import save_translations_bulk
from backend.providers.factory import get_provider
from backend.translation.orchestrator import chunk_entries
from backend.translation.pipeline import BatchError, BatchJob, run_translation_batch


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: extract
def cmd_extract(args: argparse.Namespace, adapter: ChronoArkAdapter) -> None:
    """Handle the `extract` subcommand for the base game, one mod, or all workshop mods.

    Args:
        args: Parsed CLI arguments.
        adapter: Active game adapter.
    """
    if args.base_game:
        print("Extracting base game strings...")
        strings = adapter.extract_base_game_strings()
        output_path = GameStorage(GAME_ID).root / "base_game" / "strings.json"
        save_extracted_strings(strings, output_path)
        print(f"  Saved {len(strings)} strings to {output_path}")

    elif args.mod:
        mod_path = Path(args.mod)
        # A mod folder is named after its Workshop id. A bare id is looked up instead.
        if mod_path.exists():
            mod_id = mod_path.name
        else:
            mod = adapter.find_mod(args.mod)
            if mod is None:
                print(f"Mod not found: {args.mod}")
                sys.exit(1)
            mod_id, mod_path = mod.mod_id, mod.path

        print(f"Extracting strings from mod {mod_id}...")
        diff = extract_mod(mod_id, mod_path)
        print(f"  New keys: {len(diff.new_keys)}")
        print(f"  Modified: {len(diff.modified_keys)}")
        print(f"  Removed: {len(diff.removed_keys)}")
        print(f"  Unchanged: {len(diff.unchanged_keys)}")

    elif args.all_mods:
        print("Scanning all mods...")
        mods = adapter.scan_mods()

        print(f"\n{'ID':<15} {'Name':<30} {'CSV':<5} {'DLL':<5} {'Entries':<8}")
        print("-" * 68)
        for mod in mods:
            csv_flag = "Yes" if mod.has_loc_files else "No"
            dll_flag = "Yes" if mod.has_dll else "No"
            entries = str(mod.entry_count) if mod.has_loc_files else "-"
            name = mod.name[:28] if len(mod.name) > 28 else mod.name
            print(f"{mod.mod_id:<15} {name:<30} {csv_flag:<5} {dll_flag:<5} {entries:<8}")

        for mod_info in mods:
            if mod_info.has_loc_files:
                print(f"\nExtracting: {mod_info.name} ({mod_info.mod_id})...")
                extract_mod(mod_info.mod_id, mod_info.path)
    else:
        print("Specify --base-game, --mod <id>, or --all-mods")
        sys.exit(1)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: translate
def cmd_translate(args: argparse.Namespace, adapter: ChronoArkAdapter) -> None:
    """Handle the `translate` subcommand, using translation memory and supporting a dry-run cost estimate.

    Args:
        args: Parsed CLI arguments (mod ID, provider, dry-run).
        adapter: Active game adapter.
    """
    mod_id = args.mod
    if not mod_id:
        print("Specify --mod <id>")
        sys.exit(1)

    mods = adapter.scan_mods()
    matching = [m for m in mods if m.mod_id == mod_id]
    if not matching:
        print(f"Mod not found: {mod_id}")
        sys.exit(1)

    print(f"Loading strings for mod {mod_id}...")
    strings, target_lang = load_mod_strings(mod_id)
    untranslated = adapter.get_untranslated(strings, target_lang)

    if not untranslated:
        print("All strings already have English translations!")
        return

    tm = TranslationMemory(game_id=GAME_ID)
    base_glossary = load_glossary(glossary_path(GAME_ID))
    needs_translation = []
    cached_translations = {}

    for key, loc_str in untranslated.items():
        source_lang = adapter.detect_source_language(loc_str)
        if source_lang is None:
            continue
        source_text = loc_str.translations.get(source_lang, "")

        cached = tm.lookup(source_text)
        if cached:
            cached_translations[key] = cached
        else:
            needs_translation.append((key, source_text, source_lang))

    print(f"\n  Total untranslated: {len(untranslated)}")
    print(f"  From translation memory: {len(cached_translations)}")
    print(f"  Need new translation: {len(needs_translation)}")

    if not needs_translation:
        print("All translations found in translation memory!")
        _apply_translations(mod_id, cached_translations)
        return

    provider_name = args.provider or settings.translation_provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        print(e)
        sys.exit(1)

    # Batches are per source language.
    entries_by_lang: dict[str, list[tuple[str, str]]] = {}
    for key, source_text, source_lang in needs_translation:
        if source_lang is None:
            continue
        if source_lang not in entries_by_lang:
            entries_by_lang[source_lang] = []
        entries_by_lang[source_lang].append((key, source_text))

    if args.dry_run:
        print(f"\n  Provider: {provider.name}")
        for lang, entries in entries_by_lang.items():
            cost = provider.estimate_cost(entries, **prompt_context(mod_id, lang, target_lang, base_glossary=base_glossary).provider_kwargs())
            print(f"\n  {lang} → {target_lang} ({len(entries)} strings):")
            for k, v in cost.items():
                print(f"    {k}: {v}")
        return

    print(f"\n  Using provider: {provider.name}")
    if cached_translations:
        _apply_translations(mod_id, cached_translations)

    translated = 0
    suggested = 0
    for lang, entries in entries_by_lang.items():
        print(f"\n  Translating {len(entries)} {lang} strings...")
        batches = chunk_entries(entries, settings.batch_size, settings.batch_max_chars)
        for batch_num, batch in enumerate(batches, start=1):
            print(f"    Batch {batch_num}/{len(batches)} ({len(batch)} strings)...")
            # Rebuilt per batch so terms added to the mod glossary mid-run apply.
            context = prompt_context(mod_id, lang, target_lang, base_glossary=base_glossary)
            persist = persist_batch(mod_id, provider_name, strings, batch, lang)
            job = BatchJob(mod_id=mod_id, game_id=GAME_ID, provider=provider, provider_name=provider_name, entries=batch, context=context, persist=persist)
            try:
                outcome = run_translation_batch(job)
            except BatchError as e:
                print(f"    Batch failed: {e}")
                sys.exit(1)
            translated += len(outcome.translations)
            suggested += len(outcome.suggestions)

    tm_entries = TranslationMemory(game_id=GAME_ID).get_stats()["total_entries"]
    print(f"\n  Translation memory: {tm_entries} entries ({tm.get_stats()['hit_rate_percent']}% hit rate this session)")
    print(f"  Translated {translated} strings")
    if suggested:
        print(f"  {suggested} glossary term suggestions pending review")


def _apply_translations(mod_id: str, translations: dict[str, str]) -> None:
    """Save translation-memory hits for the mod and mark them translated.

    Args:
        mod_id: Mod's Workshop id.
        translations: Key -> translated text.
    """
    save_translations_bulk(mod_id, translations, game_id=GAME_ID)

    tracker = ProgressTracker(game_id=GAME_ID)
    tracker.mark_translated(mod_id, list(translations.keys()))

    print(f"\n  Applied {len(translations)} translations")


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: status
def cmd_status(args: argparse.Namespace, adapter: ChronoArkAdapter) -> None:
    """Handle the `status` subcommand, showing one mod's progress or a summary of all extracted mods.

    Args:
        args: Parsed CLI arguments, where `args.mod` selects a single mod.
        adapter: Unused, kept for a consistent subcommand signature.
    """
    tracker = ProgressTracker(game_id=GAME_ID)

    if args.mod:
        status = tracker.get_status(args.mod)
        print(f"\nMod {args.mod}:")
        print(f"  Total strings: {status['total']}")
        print(f"  Translated: {status['translated']}")
        print(f"  Untranslated: {status['untranslated']}")
        print(f"  Progress: {status['percentage']}%")
        print(f"  Last updated: {status['last_updated']}")
    else:
        mods_dir = GameStorage(GAME_ID).mods_dir
        if not mods_dir.exists():
            print("No mods extracted yet. Run 'extract --all-mods' first.")
            return

        print(f"\n{'Mod ID':<15} {'Total':<8} {'Done':<8} {'Remain':<8} {'Progress':<10}")
        print("-" * 55)

        for mod_dir in sorted(mods_dir.iterdir()):
            if mod_dir.is_dir():
                status = tracker.get_status(mod_dir.name)
                if status["total"] > 0:
                    print(f"{mod_dir.name:<15} {status['total']:<8} {status['translated']:<8} {status['untranslated']:<8} {status['percentage']:<10}%")


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: glossary
def cmd_glossary(args: argparse.Namespace, adapter: ChronoArkAdapter) -> None:
    """Handle the `glossary` subcommand to show, build from base game strings, or add an entry.

    Args:
        args: Parsed CLI arguments with one of `--show`, `--build`, or `--add`.
        adapter: Active game adapter, used to extract base game strings when building.
    """
    if args.show:
        glossary = load_glossary(glossary_path(GAME_ID))
        print_glossary(glossary)

    elif args.build:
        print("Building glossary from base game strings...")
        strings = adapter.extract_base_game_strings()
        glossary = build_glossary_from_base_game(
            strings,
            term_categories=adapter.get_glossary_categories(),
            source_languages=adapter.source_languages,
        )
        save_glossary(glossary, glossary_path(GAME_ID))
        print_glossary(glossary)

    elif args.add:
        if len(args.add) != 2:
            print("Usage: glossary --add <source_term> <english_term>")
            sys.exit(1)

        source_term, english_term = args.add
        glossary = load_glossary(glossary_path(GAME_ID))
        add_glossary_term(glossary, english_term, {"custom": source_term})
        save_glossary(glossary, glossary_path(GAME_ID))
        print(f"  Added: {source_term} → {english_term}")

    else:
        print("Specify --show, --build, or --add <source> <english>")
        sys.exit(1)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: export
def cmd_export(args: argparse.Namespace, adapter: ChronoArkAdapter) -> None:
    """Handle the `export` subcommand, writing saved translations into the mod's files like the dashboard's Export.

    Args:
        args: Parsed CLI arguments with the mod ID.
        adapter: Active game adapter.
    """
    mod_id = args.mod
    if adapter.find_mod(mod_id) is None:
        print(f"Mod not found: {mod_id}")
        sys.exit(1)

    try:
        result = export_mod(mod_id)
    except DomainError as e:
        print(f"{e}. Run 'translate --mod {mod_id}' first.")
        sys.exit(1)

    print(f"  Applied {result['applied']} translations")
    for name in result["files_written"] + result["gdata_files_written"]:
        print(f"  Wrote {name}")
    if result["keyed_overrides_written"] or result["text_overrides_written"]:
        print(f"  Wrote {result['keyed_overrides_written']} keyed and {result['text_overrides_written']} text overrides for the injector mod")


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# CLI Setup
def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Steam Workshop Modding Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--game",
        type=str,
        default=GAME_ID,
        help=f"Game adapter to use (default: chrono_ark). Available: {', '.join(list_games()) or '(loading...)'}",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    extract_parser = subparsers.add_parser("extract", help="Extract localization strings")
    extract_group = extract_parser.add_mutually_exclusive_group(required=True)
    extract_group.add_argument("--base-game", action="store_true", help="Extract base game strings")
    extract_group.add_argument("--mod", type=str, help="Extract from a specific mod (Workshop ID)")
    extract_group.add_argument("--all-mods", action="store_true", help="Extract from all workshop mods")

    translate_parser = subparsers.add_parser("translate", help="Translate mod strings")
    translate_parser.add_argument("--mod", type=str, required=True, help="Mod Workshop ID")
    translate_parser.add_argument("--provider", type=str, choices=["claude", "openai", "deepl"], help="Translation provider (default: from config)")
    translate_parser.add_argument("--dry-run", action="store_true", help="Show cost estimate only")

    status_parser = subparsers.add_parser("status", help="Show translation progress")
    status_parser.add_argument("--mod", type=str, help="Show status for a specific mod")

    glossary_parser = subparsers.add_parser("glossary", help="Manage terminology glossary")
    glossary_group = glossary_parser.add_mutually_exclusive_group(required=True)
    glossary_group.add_argument("--show", action="store_true", help="Display current glossary")
    glossary_group.add_argument("--build", action="store_true", help="Auto-build from base game")
    glossary_group.add_argument("--add", nargs=2, metavar=("SOURCE", "ENGLISH"), help="Add a glossary entry")

    export_parser = subparsers.add_parser("export", help="Write saved translations into the mod's files")
    export_parser.add_argument("--mod", type=str, required=True, help="Mod Workshop ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    adapter = get_adapter(args.game)
    # The commands call Chrono Ark extractor and export methods that other adapters do not have.
    if not isinstance(adapter, ChronoArkAdapter):
        parser.error(f"The CLI only supports chrono_ark, not {args.game}.")

    commands = {
        "extract": cmd_extract,
        "translate": cmd_translate,
        "status": cmd_status,
        "glossary": cmd_glossary,
        "export": cmd_export,
    }

    commands[args.command](args, adapter)


if __name__ == "__main__":
    main()
