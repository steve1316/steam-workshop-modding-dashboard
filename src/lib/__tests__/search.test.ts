import { extractCategories, filterGlossaryTerms, filterMods, filterStrings, getRowStatus, matchesSearch, sortStrings } from "@/lib/search"
import type { GlossaryTerm, LocString, ModStatus } from "@/lib/types"

function makeString(overrides: Partial<LocString> = {}): LocString {
    return {
        key: "Skill/Test_Name",
        type: "Text",
        desc: "",
        source: "테스트",
        source_lang: "Korean",
        english: "",
        is_translated: false,
        original_english: "",
        is_synced: false,
        is_untouched: false,
        synced_english: "",
        source_file: "LangDataDB.csv",
        translated_by: "",
        untranslatable_reason: "",
        ...overrides,
    }
}

describe("getRowStatus", () => {
    it("returns untranslatable when untranslatable_reason is set", () => {
        expect(getRowStatus(makeString({ untranslatable_reason: "hardcoded" }))).toBe("untranslatable")
    })
    it("returns synced when is_synced is true", () => {
        expect(getRowStatus(makeString({ is_synced: true, is_translated: true, english: "Test" }))).toBe("synced")
    })
    it("returns pending when translated but not synced", () => {
        expect(getRowStatus(makeString({ is_translated: true, english: "Test" }))).toBe("pending")
    })
    it("returns missing when not translated", () => {
        expect(getRowStatus(makeString())).toBe("missing")
    })
    it("returns pending when source is empty (nothing to translate)", () => {
        expect(getRowStatus(makeString({ source: "  " }))).toBe("pending")
    })
    it("returns untouched when is_untouched is true", () => {
        expect(getRowStatus(makeString({ is_untouched: true, is_translated: true, english: "Test" }))).toBe("untouched")
    })
    it("prioritizes synced over untouched", () => {
        expect(getRowStatus(makeString({ is_synced: true, is_untouched: true, is_translated: true, english: "Test" }))).toBe("synced")
    })
    it("prioritizes untranslatable over synced", () => {
        expect(getRowStatus(makeString({ untranslatable_reason: "DLL", is_synced: true }))).toBe("untranslatable")
    })
})

describe("filterStrings", () => {
    const translated = makeString({ key: "A", is_translated: true, english: "Done" })
    const missing = makeString({ key: "B" })
    const synced = makeString({ key: "C", is_translated: true, is_synced: true, english: "Synced" })
    const emptySource = makeString({ key: "D", source: "" })
    const untranslatable = makeString({ key: "E", untranslatable_reason: "DLL", source: "中文" })
    const untouched = makeString({ key: "F", is_untouched: true, is_translated: true, english: "Original" })
    const all = [translated, missing, synced, emptySource, untranslatable, untouched]

    it("hides rows with empty source text", () => {
        expect(filterStrings(all, "all", "").map((s) => s.key)).not.toContain("D")
    })
    it("all filter shows all non-empty rows", () => {
        expect(filterStrings(all, "all", "")).toHaveLength(5)
    })
    it("missing filter excludes translated and untranslatable", () => {
        expect(filterStrings(all, "missing", "").map((s) => s.key)).toEqual(["B"])
    })
    it("pending filter shows translated-but-not-synced", () => {
        expect(filterStrings(all, "pending", "").map((s) => s.key)).toEqual(["A"])
    })
    it("untouched filter shows only untouched", () => {
        expect(filterStrings(all, "untouched", "").map((s) => s.key)).toEqual(["F"])
    })
    it("synced filter shows only synced", () => {
        expect(filterStrings(all, "synced", "").map((s) => s.key)).toEqual(["C"])
    })
    it("search matches across key", () => {
        expect(filterStrings(all, "all", "LangDataDB")).toHaveLength(5)
    })
    it("search matches source_file", () => {
        const s = makeString({ source_file: "CustomMod.csv" })
        expect(filterStrings([s], "all", "custom")).toHaveLength(1)
    })
    it("search matches english (case-insensitive)", () => {
        expect(filterStrings(all, "all", "done").map((s) => s.key)).toEqual(["A"])
    })
    it("combined filter + search", () => {
        expect(filterStrings(all, "synced", "synced").map((s) => s.key)).toEqual(["C"])
    })
})

describe("sortStrings", () => {
    const a = makeString({ key: "Alpha", english: "B" })
    const b = makeString({ key: "Beta", english: "A" })
    const c = makeString({ key: "Charlie", english: "C" })

    it("sorts ascending by key", () => {
        expect(sortStrings([c, a, b], { key: "key", direction: "asc" }).map((s) => s.key)).toEqual(["Alpha", "Beta", "Charlie"])
    })
    it("sorts descending by key", () => {
        expect(sortStrings([a, b, c], { key: "key", direction: "desc" }).map((s) => s.key)).toEqual(["Charlie", "Beta", "Alpha"])
    })
    it("returns unsorted copy when direction is null", () => {
        const input = [c, a, b]
        const result = sortStrings(input, { key: "key", direction: null })
        expect(result.map((s) => s.key)).toEqual(["Charlie", "Alpha", "Beta"])
        expect(result).not.toBe(input)
    })
    it("sorts by english field", () => {
        expect(sortStrings([a, b, c], { key: "english", direction: "asc" }).map((s) => s.english)).toEqual(["A", "B", "C"])
    })
    it("does not mutate the input array", () => {
        const input = [b, a]
        sortStrings(input, { key: "key", direction: "asc" })
        expect(input.map((s) => s.key)).toEqual(["Beta", "Alpha"])
    })
})

function makeMod(overrides: Partial<ModStatus> = {}): ModStatus {
    return {
        id: "123",
        name: "Test Mod",
        author: "Author",
        has_csv: true,
        has_dll: false,
        total: 10,
        translated: 5,
        untranslated: 5,
        user_translated: 5,
        untouched: 0,
        percentage: 50,
        last_updated: "",
        has_changes: false,
        ...overrides,
    }
}

describe("filterMods", () => {
    const mods = [makeMod({ id: "1", name: "Amethyst", author: "HEIIO" }), makeMod({ id: "2", name: "Roland", author: "Modder" }), makeMod({ id: "3", name: "Fire Pack", author: "HEIIO" })]

    it("returns all mods when search is empty", () => {
        expect(filterMods(mods, "")).toHaveLength(3)
        expect(filterMods(mods, "  ")).toHaveLength(3)
    })

    it("filters by mod name (case-insensitive)", () => {
        expect(filterMods(mods, "amethyst").map((m) => m.id)).toEqual(["1"])
    })

    it("filters by author", () => {
        expect(filterMods(mods, "heiio").map((m) => m.id)).toEqual(["1", "3"])
    })

    it("returns empty when no matches", () => {
        expect(filterMods(mods, "nonexistent")).toEqual([])
    })
})

describe("matchesSearch", () => {
    it("matches any field case-insensitively and skips null fields", () => {
        expect(matchesSearch("velo", "Double Projectile Velocity Compat", "3311361464")).toBe(true)
        expect(matchesSearch("3311361464", "Double Projectile Velocity Compat", "3311361464")).toBe(true)
        expect(matchesSearch("zzz", "Double Projectile Velocity Compat", null, undefined)).toBe(false)
    })

    it("matches everything for blank or whitespace-only search text", () => {
        expect(matchesSearch("   ", "anything")).toBe(true)
    })
})

function makeTerm(overrides: Partial<GlossaryTerm> = {}): GlossaryTerm {
    return {
        category: "skills",
        key: "",
        source_mappings: {},
        ...overrides,
    }
}

describe("extractCategories", () => {
    it("returns sorted unique categories", () => {
        const terms = {
            "Fire Bolt": makeTerm({ category: "skills" }),
            "Iron Shield": makeTerm({ category: "items" }),
            Azar: makeTerm({ category: "characters" }),
        }
        expect(extractCategories(terms)).toEqual(["characters", "items", "skills"])
    })

    it("returns empty array for empty glossary", () => {
        expect(extractCategories({})).toEqual([])
    })

    it("deduplicates repeated categories", () => {
        const terms = {
            A: makeTerm({ category: "skills" }),
            B: makeTerm({ category: "skills" }),
        }
        expect(extractCategories(terms)).toEqual(["skills"])
    })
})

describe("filterGlossaryTerms", () => {
    const terms = {
        "Fire Bolt": makeTerm({ category: "skills", key: "Skill/FireBolt", source_mappings: { Korean: "화염구" } }),
        Azar: makeTerm({ category: "characters", key: "Character/Azar", source_mappings: { Korean: "아자르" } }),
        Shield: makeTerm({ category: "items", key: "Item/Shield", source_mappings: { Korean: "방패" } }),
    }

    it("returns all terms sorted when search is empty and category is all", () => {
        expect(filterGlossaryTerms(terms, "", "all").map(([e]) => e)).toEqual(["Azar", "Fire Bolt", "Shield"])
    })

    it("matches search against English key", () => {
        expect(filterGlossaryTerms(terms, "fire", "all").map(([e]) => e)).toEqual(["Fire Bolt"])
    })

    it("matches search against source mapping values", () => {
        expect(filterGlossaryTerms(terms, "화염구", "all").map(([e]) => e)).toEqual(["Fire Bolt"])
    })

    it("matches search against glossary key field", () => {
        expect(filterGlossaryTerms(terms, "Character/Azar", "all").map(([e]) => e)).toEqual(["Azar"])
    })

    it("filters by category", () => {
        expect(filterGlossaryTerms(terms, "", "skills").map(([e]) => e)).toEqual(["Fire Bolt"])
    })

    it("combined search + category filter", () => {
        expect(filterGlossaryTerms(terms, "shield", "items").map(([e]) => e)).toEqual(["Shield"])
    })

    it("returns empty when nothing matches", () => {
        expect(filterGlossaryTerms(terms, "nonexistent", "all")).toEqual([])
    })

    it("category filter with no matching search returns empty", () => {
        expect(filterGlossaryTerms(terms, "fire", "items")).toEqual([])
    })
})
