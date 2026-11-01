"""
Steam Workshop Modding Dashboard - CLI entry point for extracting, translating, and managing mod localization strings.

Usage:
    python main.py extract --base-game
    python main.py extract --mod <id>
    python main.py extract --all-mods
    python main.py translate --mod <id> [--provider claude|openai|deepl]
    python main.py translate --mod <id> --dry-run
    python main.py status [--mod <id>]
    python main.py glossary --show|--build|--add <source> <english>
    python main.py export --mod <id>
"""

import argparse
import sys
from pathlib import Path

from backend import config
from backend.core.json_store import write_json
from backend.data.glossary_manager import (
    add_glossary_term,
    build_glossary_from_base_game,
    get_combined_glossary_prompt,
    load_glossary,
    load_mod_glossary,
    print_glossary,
    save_glossary,
)
from backend.data.progress_tracker import ProgressTracker
from backend.data.suggestion_manager import add_suggestions
from backend.data.translation_memory import TranslationMemory
from backend.data.translation_store import load_translations, save_translations_bulk
from backend.games.base import GameAdapter
from backend.games.registry import get_adapter, list_games
from backend.translation.orchestrator import chunk_entries
from backend.translator.base import TranslationProvider
from backend.translator.claude_provider import ClaudeProvider
from backend.translator.deepl_provider import DeepLProvider
from backend.translator.llamacpp_provider import LlamaCppProvider
from backend.translator.manual_provider import ManualProvider
from backend.translator.ollama_provider import OllamaProvider
from backend.translator.openai_provider import OpenAIProvider


def get_provider(provider_name: str) -> TranslationProvider:
    """Create a translation provider instance by name.

    Args:
        provider_name: One of `"claude"`, `"openai"`, `"deepl"`, `"ollama"`, `"llamacpp"`, `"manual"`.

    Returns:
        Initialized provider.
    """
    if provider_name == "claude":
        return ClaudeProvider(model=config.CLAUDE_MODEL)
    elif provider_name == "openai":
        return OpenAIProvider(model=config.OPENAI_MODEL)
    elif provider_name == "deepl":
        return DeepLProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "llamacpp":
        return LlamaCppProvider()
    elif provider_name == "manual":
        return ManualProvider()
    raise ValueError(f"Unknown provider: {provider_name}. Available: claude, openai, deepl, ollama, llamacpp, manual")


def save_extracted_strings(strings: dict, output_path: Path) -> None:
    """
    Save extracted strings to a JSON file.

    Args:
        strings: Key -> `LocString`.
        output_path: JSON file to write.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    for key, loc_str in strings.items():
        data[key] = {
            "type": loc_str.type,
            "desc": loc_str.desc,
            "translations": loc_str.translations,
            "source_file": loc_str.source_file,
        }

    write_json(output_path, data)

    print(f"  Saved {len(data)} strings to {output_path}")


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: extract
def cmd_extract(args: argparse.Namespace, adapter: GameAdapter) -> None:
    """Handle the `extract` subcommand for the base game, one mod, or all workshop mods.

    Args:
        args: Parsed CLI arguments.
        adapter: Active game adapter.
    """
    if args.base_game:
        print("Extracting base game strings...")
        strings = adapter.extract_base_game_strings()
        output_path = config.STORAGE_PATH / "base_game" / "strings.json"
        save_extracted_strings(strings, output_path)

    elif args.mod:
        mod_path = Path(args.mod)
        # A bare ID rather than a path is resolved by scanning.
        if not mod_path.exists():
            mods = adapter.scan_mods()
            matching = [m for m in mods if m.mod_id == args.mod]
            if not matching:
                print(f"Mod not found: {args.mod}")
                sys.exit(1)
            mod_path = matching[0].path

        print(f"Extracting strings from mod {args.mod}...")
        strings, _ = adapter.extract_strings(mod_path)
        output_path = config.STORAGE_PATH / "mods" / args.mod / "source.json"
        save_extracted_strings(strings, output_path)

        tracker = ProgressTracker()
        diff = tracker.update(args.mod, strings, adapter.source_languages)
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

        tracker = ProgressTracker()
        for mod_info in mods:
            if mod_info.has_loc_files:
                print(f"\nExtracting: {mod_info.name} ({mod_info.mod_id})...")
                strings, _ = adapter.extract_strings(mod_info.path)
                output = config.STORAGE_PATH / "mods" / mod_info.mod_id / "source.json"
                save_extracted_strings(strings, output)
                tracker.update(mod_info.mod_id, strings, adapter.source_languages)
    else:
        print("Specify --base-game, --mod <id>, or --all-mods")
        sys.exit(1)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: translate
def cmd_translate(args: argparse.Namespace, adapter: GameAdapter) -> None:
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
    mod_path = matching[0].path

    print(f"Loading strings for mod {mod_id}...")
    strings, _ = adapter.extract_strings(mod_path)
    untranslated = adapter.get_untranslated(strings)

    if not untranslated:
        print("All strings already have English translations!")
        return

    tm = TranslationMemory()
    base_glossary = load_glossary()
    mod_glossary = load_mod_glossary(mod_id)
    needs_translation = []
    cached_translations = {}

    for key, loc_str in untranslated.items():
        source_lang = adapter.detect_source_language(loc_str)
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
        _apply_translations(mod_id, cached_translations, tm)
        return

    provider_name = args.provider or config.TRANSLATION_PROVIDER
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        print(e)
        sys.exit(1)

    game_context = adapter.get_translation_context()
    format_rules = adapter.get_format_preservation_rules()

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
            glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang)
            cost = provider.estimate_cost(
                entries,
                source_lang=lang,
                glossary_prompt=glossary_prompt,
                game_context=game_context,
                format_rules=format_rules,
                style_examples=adapter.get_style_examples(lang),
            )
            print(f"\n  {lang} → English ({len(entries)} strings):")
            for k, v in cost.items():
                print(f"    {k}: {v}")
        return

    print(f"\n  Using provider: {provider.name}")
    all_translations = dict(cached_translations)
    all_suggestions = []

    for lang, entries in entries_by_lang.items():
        print(f"\n  Translating {len(entries)} {lang} strings...")

        batch_size = config.BATCH_SIZE
        batch_num = 1
        batches = chunk_entries(entries, batch_size, config.BATCH_MAX_CHARS)
        total_batches = len(batches)

        for batch in batches:
            print(f"    Batch {batch_num}/{total_batches} ({len(batch)} strings)...")

            glossary_prompt = get_combined_glossary_prompt(base_glossary, mod_glossary, source_lang=lang)
            translations, suggestions = provider.translate_batch(
                batch,
                lang,
                glossary_prompt,
                game_context=game_context,
                format_rules=format_rules,
                style_examples=adapter.get_style_examples(lang),
            )
            all_translations.update(translations)
            all_suggestions.extend(suggestions)

            for key, english in translations.items():
                source_text = ""
                for k, t in batch:
                    if k == key:
                        source_text = t
                        break
                if source_text and english:
                    tm.store(source_text, english, lang)

            batch_num += 1

    tm.save()
    tm_stats = tm.get_stats()
    print(f"\n  Translation memory: {tm_stats['total_entries']} entries ({tm_stats['hit_rate_percent']}% hit rate this session)")

    _apply_translations(mod_id, all_translations, tm)

    if all_suggestions:
        add_suggestions(mod_id, all_suggestions)
        print(f"  {len(all_suggestions)} glossary term suggestions pending review")


def _apply_translations(
    mod_id: str,
    translations: dict[str, str],
    tm: TranslationMemory,
) -> None:
    """
    Save translations for the mod and mark them translated.

    Args:
        mod_id: Mod's Workshop id.
        translations: Key -> English text.
        tm: Translation memory to save.
    """
    save_translations_bulk(mod_id, translations)

    tracker = ProgressTracker()
    tracker.mark_translated(mod_id, list(translations.keys()))

    print(f"\n  Applied {len(translations)} translations")

    tm.save()


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: status
def cmd_status(args: argparse.Namespace, adapter: GameAdapter) -> None:
    """Handle the `status` subcommand, showing one mod's progress or a summary of all extracted mods.

    Args:
        args: Parsed CLI arguments, where `args.mod` selects a single mod.
        adapter: Unused, kept for a consistent subcommand signature.
    """
    tracker = ProgressTracker()

    if args.mod:
        status = tracker.get_status(args.mod)
        print(f"\nMod {args.mod}:")
        print(f"  Total strings: {status['total']}")
        print(f"  Translated: {status['translated']}")
        print(f"  Untranslated: {status['untranslated']}")
        print(f"  Progress: {status['percentage']}%")
        print(f"  Last updated: {status['last_updated']}")
    else:
        mods_dir = config.STORAGE_PATH / "mods"
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
def cmd_glossary(args: argparse.Namespace, adapter: GameAdapter) -> None:
    """Handle the `glossary` subcommand to show, build from base game strings, or add an entry.

    Args:
        args: Parsed CLI arguments with one of `--show`, `--build`, or `--add`.
        adapter: Active game adapter, used to extract base game strings when building.
    """
    if args.show:
        glossary = load_glossary()
        print_glossary(glossary)

    elif args.build:
        print("Building glossary from base game strings...")
        strings = adapter.extract_base_game_strings()
        glossary = build_glossary_from_base_game(
            strings,
            term_categories=adapter.get_glossary_categories(),
            source_languages=adapter.source_languages,
        )
        save_glossary(glossary)
        print_glossary(glossary)

    elif args.add:
        if len(args.add) != 2:
            print("Usage: glossary --add <source_term> <english_term>")
            sys.exit(1)

        source_term, english_term = args.add
        glossary = load_glossary()
        add_glossary_term(glossary, english_term, {"custom": source_term})
        save_glossary(glossary)
        print(f"  Added: {source_term} → {english_term}")

    else:
        print("Specify --show, --build, or --add <source> <english>")
        sys.exit(1)


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Subcommand: export
def cmd_export(args: argparse.Namespace, adapter: GameAdapter) -> None:
    """Handle the `export` subcommand, writing translated strings back to CSV files.

    Args:
        args: Parsed CLI arguments with the mod ID.
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
    mod_path = matching[0].path

    strings, _ = adapter.extract_strings(mod_path)

    translations = load_translations(mod_id)
    if not translations:
        print(f"No translations found for mod {mod_id}. Run 'translate --mod {mod_id}' first.")
        sys.exit(1)

    for key, english in translations.items():
        if key in strings:
            strings[key].translations["English"] = english

    export_dir = config.STORAGE_PATH / "mods" / mod_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    by_source: dict[str, list] = {}
    for loc_str in strings.values():
        source = loc_str.source_file or adapter.csv_for_key(loc_str.key)
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(loc_str)

    for csv_filename, entries in by_source.items():
        output_path = export_dir / csv_filename
        adapter.export_strings(output_path, entries)
        print(f"  Exported {csv_filename}: {len(entries)} entries → {output_path}")

    print(f"\n  Export complete: {export_dir}")


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
        default=config.ACTIVE_GAME,
        help=f"Game adapter to use (default: {config.ACTIVE_GAME}). Available: {', '.join(list_games()) or '(loading...)'}",
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

    export_parser = subparsers.add_parser("export", help="Export translated CSV files")
    export_parser.add_argument("--mod", type=str, required=True, help="Mod Workshop ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    adapter = get_adapter(args.game)

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
