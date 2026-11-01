"""libcst-based mutator for the `SUPPORTED_MODS` list inside `helper_scripts/supported_mods.py`.

Exposes pure `add_entry`, `update_entry` and `remove_entry` functions that take the file text and return new text.
Preserves comments, formatting and the `f"{STEAM_LIBRARY_DRIVE}/.../<workshop_id>/<package_name>"` path expression the existing entries use.
"""

from __future__ import annotations

from typing import Any

import libcst as cst

_TW3_APPID_FOLDER = "1142710"
_PATH_PREFIX = "SteamLibrary/steamapps/workshop/content"
_SUPPORTED_MODS_NAME = "SUPPORTED_MODS"


class WriterError(Exception):
    """Base exception for the SUPPORTED_MODS writer."""


class EntryNotFoundError(WriterError):
    """A `package_name` is not present in the list."""


class DuplicatePackageError(WriterError):
    """An added entry's `package_name` already exists."""


def _build_path_fstring(workshop_id: str, package_name: str) -> cst.FormattedString:
    """Build the f-string node for a workshop path.

    Produces `f"{STEAM_LIBRARY_DRIVE}/SteamLibrary/steamapps/workshop/content/1142710/<workshop_id>/<package_name>"`.

    Args:
        workshop_id: Numeric Workshop item id.
        package_name: Mod's `.pack` filename.

    Returns:
        Node ready for a `cst.DictElement`.
    """
    return cst.FormattedString(
        parts=[
            cst.FormattedStringExpression(expression=cst.Name("STEAM_LIBRARY_DRIVE")),
            cst.FormattedStringText(value=f"/{_PATH_PREFIX}/{_TW3_APPID_FOLDER}/{workshop_id}/{package_name}"),
        ],
        start='f"',
        end='"',
    )


def _value_to_cst(value: Any) -> cst.BaseExpression:
    """Convert a Python value (`str`, `bool`, `int`, `list`, `dict`) to a libcst expression node, with strings double-quoted.

    Args:
        value: JSON-compatible value.

    Returns:
        libcst expression node.
    """
    if isinstance(value, str):
        # JSON-style double-quoted string
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return cst.SimpleString(f'"{escaped}"')
    if isinstance(value, bool):
        # bool must come before int since bool is a subclass of int
        return cst.Name("True") if value else cst.Name("False")
    if isinstance(value, int):
        return cst.Integer(str(value))
    if isinstance(value, list):
        return cst.List(elements=[cst.Element(value=_value_to_cst(item)) for item in value])
    if isinstance(value, dict):
        return cst.Dict(elements=[cst.DictElement(key=_value_to_cst(str(k)), value=_value_to_cst(v)) for k, v in value.items()])
    raise WriterError(f"Unsupported value type: {type(value).__name__}")


def _build_entry_dict(entry: dict) -> cst.Dict:
    """Build a `cst.Dict` for a SUPPORTED_MODS entry, with `path` handled specially.

    Without a truthy `custom_path`, an entry with `workshop_id` gets the standard f-string `path`.
    Otherwise `path` is a plain string literal (e.g. `vanilla` has an empty path).

    Args:
        entry: Frontend payload needing `name`, `package_name` and `modified_attributes`, and optionally `workshop_id`, `path`, `pattern_overrides`,
            `character_overrides`, `ignore_generation`.

    Returns:
        Dict to insert into the SUPPORTED_MODS list.
    """
    elements: list[cst.DictElement] = []
    workshop_id = entry.get("workshop_id") or ""
    package_name = entry.get("package_name", "")
    custom_path = entry.get("path") if entry.get("custom_path") else None

    elements.append(cst.DictElement(key=_value_to_cst("name"), value=_value_to_cst(entry["name"])))
    elements.append(cst.DictElement(key=_value_to_cst("package_name"), value=_value_to_cst(package_name)))
    if custom_path is not None:
        elements.append(cst.DictElement(key=_value_to_cst("path"), value=_value_to_cst(custom_path)))
    elif workshop_id:
        elements.append(cst.DictElement(key=_value_to_cst("path"), value=_build_path_fstring(workshop_id, package_name)))
    else:
        elements.append(cst.DictElement(key=_value_to_cst("path"), value=_value_to_cst("")))
    elements.append(cst.DictElement(key=_value_to_cst("modified_attributes"), value=_value_to_cst(entry.get("modified_attributes", []))))
    if "pattern_overrides" in entry and entry["pattern_overrides"]:
        elements.append(cst.DictElement(key=_value_to_cst("pattern_overrides"), value=_value_to_cst(entry["pattern_overrides"])))
    if "character_overrides" in entry and entry["character_overrides"]:
        elements.append(cst.DictElement(key=_value_to_cst("character_overrides"), value=_value_to_cst(entry["character_overrides"])))
    if entry.get("ignore_generation"):
        elements.append(cst.DictElement(key=_value_to_cst("ignore_generation"), value=_value_to_cst(True)))

    return cst.Dict(elements=elements)


def _find_supported_mods_list(module: cst.Module) -> cst.List:
    """Locate the `SUPPORTED_MODS = [...]` assignment's list literal.

    Args:
        module: Parsed libcst module.

    Returns:
        The `cst.List` node.
    """
    for stmt in module.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if not isinstance(small, cst.Assign):
                continue
            for target in small.targets:
                if isinstance(target.target, cst.Name) and target.target.value == _SUPPORTED_MODS_NAME:
                    if not isinstance(small.value, cst.List):
                        raise WriterError(f"{_SUPPORTED_MODS_NAME} is not a list literal")
                    return small.value
    raise WriterError(f"{_SUPPORTED_MODS_NAME} assignment not found")


def _entry_package_name(dict_node: cst.Dict) -> str | None:
    """Read the `package_name` field from a `cst.Dict` entry.

    Args:
        dict_node: SUPPORTED_MODS entry dict.

    Returns:
        The package_name, or None when missing or not a SimpleString.
    """
    for element in dict_node.elements:
        if not isinstance(element, cst.DictElement):
            continue
        key = element.key
        if isinstance(key, cst.SimpleString) and key.evaluated_value == "package_name":
            value = element.value
            if isinstance(value, cst.SimpleString):
                return value.evaluated_value
    return None


def _replace_supported_mods_list(module: cst.Module, new_list: cst.List) -> cst.Module:
    """Return a new `cst.Module` with the SUPPORTED_MODS list replaced.

    Args:
        module: Source module.
        new_list: Replacement list literal.

    Returns:
        Mutated module.
    """

    class _Transformer(cst.CSTTransformer):
        def leave_Assign(self, original: cst.Assign, updated: cst.Assign) -> cst.Assign:
            for target in updated.targets:
                if isinstance(target.target, cst.Name) and target.target.value == _SUPPORTED_MODS_NAME:
                    return updated.with_changes(value=new_list)
            return updated

    return module.visit(_Transformer())


def add_entry(source: str, entry: dict) -> str:
    """Append a new SUPPORTED_MODS entry.

    Args:
        source: Current `supported_mods.py` text.
        entry: Frontend entry payload (see `_build_entry_dict`).

    Returns:
        New source text.
    """
    module = cst.parse_module(source)
    list_node = _find_supported_mods_list(module)
    package_name = entry.get("package_name", "")
    for element in list_node.elements:
        if isinstance(element.value, cst.Dict) and _entry_package_name(element.value) == package_name:
            raise DuplicatePackageError(package_name)
    new_dict = _build_entry_dict(entry)
    new_list = list_node.with_changes(elements=list(list_node.elements) + [cst.Element(value=new_dict)])
    return _replace_supported_mods_list(module, new_list).code


def update_entry(source: str, package_name: str, entry: dict) -> str:
    """Replace the entry keyed by `package_name`.

    Args:
        source: Current `supported_mods.py` text.
        package_name: Package name of the entry to replace.
        entry: Replacement entry payload.

    Returns:
        New source text.
    """
    module = cst.parse_module(source)
    list_node = _find_supported_mods_list(module)
    new_dict = _build_entry_dict(entry)
    new_elements = []
    found = False
    for element in list_node.elements:
        if isinstance(element.value, cst.Dict) and _entry_package_name(element.value) == package_name:
            new_elements.append(element.with_changes(value=new_dict))
            found = True
        else:
            new_elements.append(element)
    if not found:
        raise EntryNotFoundError(package_name)
    new_list = list_node.with_changes(elements=new_elements)
    return _replace_supported_mods_list(module, new_list).code


def remove_entry(source: str, package_name: str) -> str:
    """Remove the entry keyed by `package_name`.

    Args:
        source: Current `supported_mods.py` text.
        package_name: Package name of the entry to remove.

    Returns:
        New source text.
    """
    module = cst.parse_module(source)
    list_node = _find_supported_mods_list(module)
    new_elements = [element for element in list_node.elements if not (isinstance(element.value, cst.Dict) and _entry_package_name(element.value) == package_name)]
    if len(new_elements) == len(list_node.elements):
        raise EntryNotFoundError(package_name)
    new_list = list_node.with_changes(elements=new_elements)
    return _replace_supported_mods_list(module, new_list).code
