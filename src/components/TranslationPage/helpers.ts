import type { ReactNode, CSSProperties } from "react"
import type { ColumnDef } from "@/components/TranslationPage/types"
import type { RowStatus } from "@/lib/search"

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

/**
 * Background tint for a translation table row.
 * @param status - Row status.
 * @param opts - `override` marks an unsynced edit, where the translation differs from the synced value.
 * @returns The style, or undefined for no tint.
 */
export function canonicalRowStyle(status: RowStatus, opts: { override?: boolean } = {}): CSSProperties | undefined {
    if (status === "untranslatable") return { backgroundColor: "rgba(148, 163, 184, 0.1)" }
    if (status === "synced") return { backgroundColor: "rgba(52, 211, 153, 0.1)" }
    if (status === "changed") return { backgroundColor: "rgba(249, 115, 22, 0.1)" }
    if (opts.override) return { backgroundColor: "rgba(255, 220, 40, 0.15)" }
    return undefined
}

/** A status badge's display label and the CSS class (from index.css) that colors it. */
export interface StatusChip {
    label: string
    /** CSS class name applied alongside `status-badge`. */
    className: string
}

/** Canonical status -> badge label and class. */
const CHIPS: Record<RowStatus, StatusChip> = {
    synced: { label: "SYNCED", className: "status-synced" },
    untouched: { label: "UNTOUCHED", className: "status-untouched" },
    pending: { label: "PENDING", className: "status-translated" },
    changed: { label: "CHANGED", className: "status-changed" },
    missing: { label: "MISSING", className: "status-missing" },
    untranslatable: { label: "N/A", className: "status-untranslatable" },
}

/**
 * Map a row status to its badge label and CSS class.
 * @param status - Row status.
 * @returns The chip.
 */
export function statusToChip(status: RowStatus): StatusChip {
    return CHIPS[status]
}
