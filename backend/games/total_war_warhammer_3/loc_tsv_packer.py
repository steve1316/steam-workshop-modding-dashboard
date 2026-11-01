"""Build a WH3 translation mod's published `.pack` from its loose `.loc.tsv` files via the RPFM CLI.

Mirrors the subprocess pattern in `loc_extractor.py`. Used by `/sync` to rebuild the pack after the loose-file writeback.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core.settings import settings
from backend.games.total_war_warhammer_3.translation_mods import WH3TranslationMod


class PackBuildError(Exception):
    """Base for all recoverable pack-rebuild failures, which are non-fatal to the sync."""


class RpfmNotConfiguredError(PackBuildError):
    """`rpfm_cli` could not be resolved to a file on disk."""


class PackNotFoundError(PackBuildError):
    """No `.pack` exists in the mod's workshop content directory, or the directory is missing."""


class AmbiguousPackError(PackBuildError):
    """More than one `.pack` exists, so the target is ambiguous."""


class RpfmFailedError(PackBuildError):
    """The `rpfm_cli` subprocess returned a non-zero exit code."""


class MalformedLocTsvError(PackBuildError):
    """A loose `.loc.tsv` data row is not a single 3-column line (e.g. an unescaped embedded newline)."""


def validate_loc_tsv_dir(local_source_dir: Path) -> None:
    """Reject loose `.loc.tsv` files with malformed data rows before they reach RPFM.

    RPFM parses line by line, so an embedded newline imports as bogus rows with stray text in the key column.
    Every non-blank, non-`#` line must have exactly two tabs. This is a defensive guard, since the writeback escapes specials.

    Args:
        local_source_dir: Mod's loose source directory, scanned recursively.
    """
    for tsv in sorted(local_source_dir.rglob("*.loc.tsv")):
        for line_no, line in enumerate(tsv.read_text(encoding="utf-8").splitlines()):
            if not line or line.startswith("#"):
                continue
            if line.count("\t") != 2:
                raise MalformedLocTsvError(f"malformed loc row in {tsv} line {line_no + 1}: expected 3 tab-separated columns")


def resolve_target_pack(workshop_content_dir: Path) -> Path:
    """Return the single `.pack` inside the workshop content directory.

    Args:
        workshop_content_dir: Mod's local Workshop content folder.

    Returns:
        The one `.pack` file.
    """
    if not workshop_content_dir.exists():
        raise PackNotFoundError(f"workshop content dir does not exist: {workshop_content_dir}")
    packs = sorted(workshop_content_dir.glob("*.pack"))
    if not packs:
        raise PackNotFoundError(f"no .pack found in {workshop_content_dir}")
    if len(packs) > 1:
        raise AmbiguousPackError(f"multiple .pack files in {workshop_content_dir}; cannot pick target")
    return packs[0]


def resolve_rpfm_cli_path() -> Path | None:
    """Resolve `rpfm_cli` like the extract path: `config.TW3_RPFM_CLI_PATH`, else `<TW3_HELPER_PATH>/rpfm_cli.exe`.

    Returns:
        Path when it resolves to a file, else None.
    """
    rpfm_str = settings.tw3.rpfm_cli_path or ""
    if rpfm_str:
        rpfm: Path | None = Path(rpfm_str)
    else:
        helper_str = settings.tw3.helper_path or ""
        rpfm = Path(helper_str) / "rpfm_cli.exe" if helper_str else None
    if rpfm is None or not rpfm.is_file():
        return None
    return rpfm


def _run_rpfm(rpfm_cli_path: Path, args: list[str]) -> None:
    """Run `rpfm_cli --game warhammer_3 <args>` from the exe's directory, raising on non-zero exit.

    Args:
        rpfm_cli_path: `rpfm_cli.exe` path.
        args: Arguments after `--game warhammer_3`.
    """
    cmd = [str(rpfm_cli_path), "--game", "warhammer_3", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, cwd=str(rpfm_cli_path.parent))
    except OSError as exc:
        raise RpfmFailedError(f"failed to launch rpfm_cli: {exc}") from exc
    if result.returncode != 0:
        raise RpfmFailedError(f"RPFM failed (exit {result.returncode}): {result.stderr.decode('utf-8', errors='replace')}")


def build_translation_pack(mod: WH3TranslationMod, *, rpfm_cli_path: Path, workshop_content_dir: Path) -> Path:
    """Patch the mod's published `.pack` from its loose `local_source_dir/text` via RPFM.

    Clears the pack's `text` folder so removed or renamed keys don't linger, then re-adds the source, converting each `.loc.tsv` via `--tsv-to-binary`.

    Args:
        mod: Translation mod whose pack to rebuild.
        rpfm_cli_path: `rpfm_cli.exe` path.
        workshop_content_dir: Mod's local Workshop content folder holding its `.pack`.

    Returns:
        Rebuilt `.pack` path.
    """
    if not rpfm_cli_path.is_file():
        raise RpfmNotConfiguredError(f"rpfm_cli not found: {rpfm_cli_path}")
    validate_loc_tsv_dir(mod.local_source_dir)
    pack = resolve_target_pack(workshop_content_dir)
    schema_path = rpfm_cli_path.parent / "schemas" / "schema_wh3.ron"
    _run_rpfm(rpfm_cli_path, ["pack", "delete", "--pack-path", str(pack), "--folder-path", "text"])
    _run_rpfm(rpfm_cli_path, ["pack", "add", "--pack-path", str(pack), "--tsv-to-binary", str(schema_path), "--folder-path", f"{mod.local_source_dir};"])
    return pack
