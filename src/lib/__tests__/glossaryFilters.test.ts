import { extractCategories, filterGlossaryTerms } from "@/lib/glossaryFilters"
import type { GlossaryTerm } from "@/lib/types"

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
            "Azar": makeTerm({ category: "characters" }),
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
        "Azar": makeTerm({ category: "characters", key: "Character/Azar", source_mappings: { Korean: "아자르" } }),
        "Shield": makeTerm({ category: "items", key: "Item/Shield", source_mappings: { Korean: "방패" } }),
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
