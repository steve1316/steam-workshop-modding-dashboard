"""FK (foreign-key) validator for the TW3 mod registry."""

from pathlib import Path
from typing import Literal, TypedDict

# Base-game entry in SUPPORTED_MODS. It has no pack on disk, so an empty path is expected.
VANILLA_PACKAGE_NAME = "vanilla"


class Issue(TypedDict):
    """One broken cross-reference flagged by `validate_registries`.

    Fields:
        kind: Which of the two checks flagged it.
        severity: Always 'error', kept for forward compatibility.
        mod_package_name: Stable identity key for the mod.
        mod_name: Display name.
        target: The bad reference: missing effect category name, or missing path string.
        message: One-line description for direct UI display.
    """

    kind: Literal["missing_effect_category", "missing_mod_path"]
    severity: Literal["error"]
    mod_package_name: str
    mod_name: str
    target: str
    message: str


def _is_file_safe(path: str) -> bool:
    """Return True if `path` is an existing file, swallowing any OSError so nothing propagates out of the validator.

    @param path: Path string to check.
    @returns: True if the file exists.
    """
    try:
        return Path(path).is_file()
    except OSError:
        return False


def validate_registries(mods: list[dict], effects: dict) -> list[Issue]:
    """Validate cross-references in the mod and effects registries.

    Each `modified_attributes` entry that is not a key in `effects` gives a `missing_effect_category` issue. A missing, None or empty `path` gives a
    `missing_mod_path` issue with `target=""` (except the vanilla entry, which has no pack by design), and a path not on disk gives one with `target=path`.

    @param mods: Mod dicts from `load_supported_mods`.
    @param effects: Effect categories from `load_supported_effects`.
    @returns: `Issue` dicts sorted by `(mod_name, kind, target)`.
    """
    issues: list[Issue] = []

    for mod in mods:
        mod_package_name: str = mod.get("package_name", "")
        mod_name: str = mod.get("name", "")

        modified_attributes = mod.get("modified_attributes")
        if modified_attributes:
            for entry in modified_attributes:
                category = str(entry)
                if category not in effects:
                    issues.append(
                        Issue(
                            kind="missing_effect_category",
                            severity="error",
                            mod_package_name=mod_package_name,
                            mod_name=mod_name,
                            target=category,
                            message=f"modified_attributes references '{category}' but no such category exists in SUPPORTED_EFFECTS",
                        )
                    )

        # Path check. The vanilla entry has no pack on disk by design, so its empty path is not an issue.
        path = mod.get("path")
        if not path:
            if mod_package_name == VANILLA_PACKAGE_NAME:
                continue
            issues.append(
                Issue(
                    kind="missing_mod_path",
                    severity="error",
                    mod_package_name=mod_package_name,
                    mod_name=mod_name,
                    target="",
                    message="path field is missing or empty",
                )
            )
        elif not _is_file_safe(path):
            issues.append(
                Issue(
                    kind="missing_mod_path",
                    severity="error",
                    mod_package_name=mod_package_name,
                    mod_name=mod_name,
                    target=path,
                    message=f"path '{path}' does not exist on disk",
                )
            )

    return sorted(issues, key=lambda i: (i["mod_name"], i["kind"], i["target"]))
