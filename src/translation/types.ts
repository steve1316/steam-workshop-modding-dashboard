import type { ReactNode } from "react"

/** Definition of one column in the shared strings table. */
export interface ColumnDef<Row> {
    /** Field id, used as the React key and sort key. */
    field: string
    label: string
    width: number
    /** Whether clicking the header sorts by this column. */
    sortable?: boolean
    /** CSS class on this column's `<td>` (e.g. "key-cell") for typography and wrapping. */
    cellClassName?: string
    render: (row: Row) => ReactNode
}
