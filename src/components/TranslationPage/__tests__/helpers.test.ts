import { TRANSLATION_COLUMN_WIDTHS, translationColumns, canonicalRowStyle, statusToChip } from "@/components/TranslationPage/helpers"
import { describe, expect, it } from "vitest"

/**
 * A cell spec that renders the field name.
 *
 * @param field Row field id.
 * @returns The spec.
 */
const cell = (field: string) => ({ field, render: () => field })

describe("translationColumns", () => {
    it("builds CA's six columns in order with CA's widths, classes and labels", () => {
        const cols = translationColumns(
            { status: cell("status"), mode: cell("provider"), source: cell("file"), key: cell("key"), original: cell("parent"), translation: cell("text") },
            { original: "Original (Chinese)", translation: "English" }
        )
        expect(cols.map((c) => c.label)).toEqual(["Status", "Mode", "Source", "Key", "Original (Chinese)", "English"])
        expect(cols.map((c) => c.field)).toEqual(["status", "provider", "file", "key", "parent", "text"])
        expect(cols.map((c) => c.width)).toEqual(Object.values(TRANSLATION_COLUMN_WIDTHS))
        expect(cols.map((c) => c.cellClassName)).toEqual([undefined, "key-cell", "key-cell", "key-cell", "source-cell", "english-cell"])
        expect(cols.every((c) => c.sortable)).toBe(true)
        expect(cols[1].render({})).toBe("provider")
    })
})

describe("canonicalRowStyle", () => {
    it("tints untranslatable grey, synced green, override yellow", () => {
        expect(canonicalRowStyle("untranslatable")).toEqual({ backgroundColor: "rgba(148, 163, 184, 0.1)" })
        expect(canonicalRowStyle("synced")).toEqual({ backgroundColor: "rgba(52, 211, 153, 0.1)" })
        expect(canonicalRowStyle("pending", { override: true })).toEqual({ backgroundColor: "rgba(255, 220, 40, 0.15)" })
    })

    it("tints changed rows orange", () => {
        expect(canonicalRowStyle("changed")).toEqual({ backgroundColor: "rgba(249, 115, 22, 0.1)" })
    })

    it("returns undefined for plain missing/untouched rows", () => {
        expect(canonicalRowStyle("missing")).toBeUndefined()
        expect(canonicalRowStyle("untouched")).toBeUndefined()
    })
})

describe("statusToChip", () => {
    it("maps each canonical status to Chrono Ark's badge label and CSS class", () => {
        expect(statusToChip("synced")).toEqual({ label: "SYNCED", className: "status-synced" })
        expect(statusToChip("untouched")).toEqual({ label: "UNTOUCHED", className: "status-untouched" })
        expect(statusToChip("pending")).toEqual({ label: "PENDING", className: "status-translated" })
        expect(statusToChip("changed")).toEqual({ label: "CHANGED", className: "status-changed" })
        expect(statusToChip("missing")).toEqual({ label: "MISSING", className: "status-missing" })
        expect(statusToChip("untranslatable")).toEqual({ label: "N/A", className: "status-untranslatable" })
    })
})
