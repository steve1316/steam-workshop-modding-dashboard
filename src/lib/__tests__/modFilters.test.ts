import { filterMods, matchesSearch } from "@/lib/modFilters"
import type { ModStatus } from "@/lib/types"

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
    const mods = [
        makeMod({ id: "1", name: "Amethyst", author: "HEIIO" }),
        makeMod({ id: "2", name: "Roland", author: "Modder" }),
        makeMod({ id: "3", name: "Fire Pack", author: "HEIIO" }),
    ]

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
