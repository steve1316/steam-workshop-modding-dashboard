import { getRowStatus, getRowStyle, filterStrings, sortStrings } from "@/utils/stringFilters"
import type { LocString } from "@/shared_types"

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

describe("getRowStyle", () => {
    it("returns grey for untranslatable", () => {
        expect(getRowStyle(makeString({ untranslatable_reason: "hardcoded" }))).toEqual({ backgroundColor: "rgba(148, 163, 184, 0.1)" })
    })
    it("returns green for synced", () => {
        expect(getRowStyle(makeString({ is_synced: true }))).toEqual({ backgroundColor: "rgba(52, 211, 153, 0.1)" })
    })
    it("returns yellow for override", () => {
        expect(getRowStyle(makeString({ english: "New", original_english: "Old" }))).toEqual({ backgroundColor: "rgba(255, 220, 40, 0.15)" })
    })
    it("returns undefined for untouched", () => {
        expect(getRowStyle(makeString({ is_untouched: true }))).toBeUndefined()
    })
    it("returns undefined for default rows", () => {
        expect(getRowStyle(makeString())).toBeUndefined()
    })
    it("returns undefined when english matches original", () => {
        expect(getRowStyle(makeString({ english: "Same", original_english: "Same" }))).toBeUndefined()
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
