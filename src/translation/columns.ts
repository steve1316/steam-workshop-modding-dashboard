import type { ReactNode } from "react"

import type { ColumnDef } from "@/translation/types"

/** One translation-table cell: the row field it sorts by and how it renders. */
export interface TranslationCellSpec<Row> {
    /** Row field id, for sorting and width persistence. */
    field: string
    render: (row: Row) => ReactNode
}

/** The six columns every translation page shows, left to right. */
export interface TranslationColumnSpecs<Row> {
    status: TranslationCellSpec<Row>
    /** Who translated the row (e.g. claude, manual). */
    mode: TranslationCellSpec<Row>
    source: TranslationCellSpec<Row>
    key: TranslationCellSpec<Row>
    /** Original source text. */
    original: TranslationCellSpec<Row>
    /** Editable translation. */
    translation: TranslationCellSpec<Row>
}

/** Column header labels that depend on the mod's languages. */
export interface TranslationColumnLabels {
    /** Original text header, e.g. "Original (Chinese)". */
    original: string
    /** Translation header, e.g. "English". */
    translation: string
}

/** Chrono Ark's default column widths in pixels, used by every game. */
export const TRANSLATION_COLUMN_WIDTHS = { status: 120, mode: 100, source: 100, key: 200, original: 400, translation: 500 } as const

/**
 * Build the standard translation-table columns. Each game supplies only its fields and cell renderers.
 *
 * @param specs - Field id and renderer per column.
 * @param labels - Language-dependent header labels.
 * @returns The `StringsTable` columns.
 */
export function translationColumns<Row>(specs: TranslationColumnSpecs<Row>, labels: TranslationColumnLabels): ColumnDef<Row>[] {
    const w = TRANSLATION_COLUMN_WIDTHS
    return [
        { ...specs.status, label: "Status", width: w.status, sortable: true },
        { ...specs.mode, label: "Mode", width: w.mode, sortable: true, cellClassName: "key-cell" },
        { ...specs.source, label: "Source", width: w.source, sortable: true, cellClassName: "key-cell" },
        { ...specs.key, label: "Key", width: w.key, sortable: true, cellClassName: "key-cell" },
        { ...specs.original, label: labels.original, width: w.original, sortable: true, cellClassName: "source-cell" },
        { ...specs.translation, label: labels.translation, width: w.translation, sortable: true, cellClassName: "english-cell" },
    ]
}
