import { describe, expect, it } from "vitest"

import { TRANSLATION_COLUMN_WIDTHS, translationColumns } from "@/components/TranslationPage/columns"

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
