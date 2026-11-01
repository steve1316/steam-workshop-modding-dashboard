"""Tests for the TW3 FK validator."""

from pathlib import Path

from backend.games.total_war_warhammer_3.registry.validator import validate_registries

# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Helpers


def _mod(name: str, package_name: str, **kwargs) -> dict:
    """Build a minimal mod dict with required identity fields plus any extras.

    @param name: Human-readable display name.
    @param package_name: Stable identity key.
    @param kwargs: Additional fields to merge into the dict.
    @returns: A mod dict suitable for passing to `validate_registries`.
    """
    return {"name": name, "package_name": package_name, **kwargs}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Category check tests


def test_empty_registries_yields_no_issues():
    """No mods and no effects should produce zero issues."""
    issues = validate_registries([], {})
    assert issues == []


def test_mod_with_no_modified_attributes_passes_category_check():
    """Covers missing field, None, and empty list - all should skip the category check."""
    effects = {"infantry": {}}
    mods = [
        _mod("Mod A", "mod_a"),  # missing modified_attributes field
        _mod("Mod B", "mod_b", modified_attributes=None),
        _mod("Mod C", "mod_c", modified_attributes=[]),
    ]
    issues = validate_registries(mods, effects)
    category_issues = [i for i in issues if i["kind"] == "missing_effect_category"]
    assert category_issues == []


def test_missing_effect_category_emits_issue():
    effects = {"infantry": {}}
    mods = [_mod("Mod A", "mod_a", path="/fake/a.pack", modified_attributes=["melee"])]
    issues = validate_registries(mods, effects)
    category_issues = [i for i in issues if i["kind"] == "missing_effect_category"]
    assert len(category_issues) == 1
    issue = category_issues[0]
    assert issue["kind"] == "missing_effect_category"
    assert issue["severity"] == "error"
    assert issue["mod_package_name"] == "mod_a"
    assert issue["mod_name"] == "Mod A"
    assert issue["target"] == "melee"
    assert issue["message"] == "modified_attributes references 'melee' but no such category exists in SUPPORTED_EFFECTS"


def test_present_effect_category_emits_no_issue():
    effects = {"melee": {}, "infantry": {}}
    mods = [_mod("Mod A", "mod_a", path="/fake/a.pack", modified_attributes=["melee", "infantry"])]
    issues = validate_registries(mods, effects)
    category_issues = [i for i in issues if i["kind"] == "missing_effect_category"]
    assert category_issues == []


def test_multiple_missing_categories_for_one_mod():
    effects = {"infantry": {}}
    mods = [_mod("Mod A", "mod_a", path="/fake/a.pack", modified_attributes=["melee", "cavalry", "artillery"])]
    issues = validate_registries(mods, effects)
    category_issues = [i for i in issues if i["kind"] == "missing_effect_category"]
    assert len(category_issues) == 3
    targets = {i["target"] for i in category_issues}
    assert targets == {"melee", "cavalry", "artillery"}


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Path check tests


def test_missing_path_field_emits_issue():
    """Covers missing field, None, and empty string - all should emit missing_mod_path with target=''."""
    mods = [
        _mod("Mod A", "mod_a"),  # missing path field
        _mod("Mod B", "mod_b", path=None),
        _mod("Mod C", "mod_c", path=""),
    ]
    issues = validate_registries(mods, {})
    path_issues = [i for i in issues if i["kind"] == "missing_mod_path"]
    assert len(path_issues) == 3
    assert {i["mod_name"] for i in path_issues} == {"Mod A", "Mod B", "Mod C"}
    for issue in path_issues:
        assert issue["severity"] == "error"
        assert issue["target"] == ""
        assert issue["message"] == "path field is missing or empty"


def test_vanilla_entry_with_empty_path_emits_no_issue():
    """The vanilla entry has no pack on disk by design, so an empty path is not flagged."""
    mods = [
        _mod("Vanilla", "vanilla"),
        _mod("Vanilla", "vanilla", path=None),
        _mod("Vanilla", "vanilla", path=""),
    ]
    issues = validate_registries(mods, {})
    assert issues == []


def test_vanilla_entry_with_nonexistent_path_still_emits_issue():
    """Only the empty-path case is exempt for vanilla - a set but broken path is still flagged."""
    mods = [_mod("Vanilla", "vanilla", path="/nonexistent/vanilla.pack")]
    issues = validate_registries(mods, {})
    assert [i["target"] for i in issues] == ["/nonexistent/vanilla.pack"]


def test_existing_path_emits_no_issue(tmp_path: Path):
    real_file = tmp_path / "real.pack"
    real_file.write_bytes(b"x")
    mods = [_mod("Mod A", "mod_a", path=str(real_file))]
    issues = validate_registries(mods, {})
    assert issues == []


def test_nonexistent_path_emits_issue():
    mods = [_mod("Mod A", "mod_a", path="/nonexistent/fake.pack")]
    issues = validate_registries(mods, {})
    path_issues = [i for i in issues if i["kind"] == "missing_mod_path"]
    assert len(path_issues) == 1
    issue = path_issues[0]
    assert issue["kind"] == "missing_mod_path"
    assert issue["severity"] == "error"
    assert issue["mod_package_name"] == "mod_a"
    assert issue["mod_name"] == "Mod A"
    assert issue["target"] == "/nonexistent/fake.pack"
    assert issue["message"] == "path '/nonexistent/fake.pack' does not exist on disk"


# //////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////
# Sort and combined tests


def test_issues_sorted_by_mod_name_then_kind_then_target():
    """Verify sort order is (mod_name, kind, target) for all three sort keys.

    Alpha Mod gets two missing categories (exercises target ordering within same name+kind)
    plus a bad path (exercises kind ordering). Zeta Mod gets one missing category and a bad
    path. Mods are given to validate_registries in reverse order to confirm input order is ignored.
    """
    effects = {}
    mods = [
        _mod("Zeta Mod", "zeta", path="/fake/z.pack", modified_attributes=["cavalry"]),
        _mod("Alpha Mod", "alpha", path="/fake/a.pack", modified_attributes=["archer", "berserker"]),
    ]
    issues = validate_registries(mods, effects)
    expected = [
        ("Alpha Mod", "missing_effect_category", "archer"),
        ("Alpha Mod", "missing_effect_category", "berserker"),
        ("Alpha Mod", "missing_mod_path", "/fake/a.pack"),
        ("Zeta Mod", "missing_effect_category", "cavalry"),
        ("Zeta Mod", "missing_mod_path", "/fake/z.pack"),
    ]
    assert [(i["mod_name"], i["kind"], i["target"]) for i in issues] == expected


def test_both_kinds_for_one_mod():
    """A mod with a missing effect category AND a nonexistent path emits both issue kinds."""
    effects = {"infantry": {}}
    mods = [_mod("Mod A", "mod_a", path="/nonexistent/fake.pack", modified_attributes=["cavalry"])]
    issues = validate_registries(mods, effects)
    kinds = {i["kind"] for i in issues}
    assert kinds == {"missing_effect_category", "missing_mod_path"}
    assert len(issues) == 2
