import { useRef } from "react"
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react"
import { FaSort, FaSortUp, FaSortDown } from "react-icons/fa"
import type { ColumnDef } from "./types"

/** Props for StringsTable. */
interface StringsTableProps<Row> {
    /** Rows to display (already filtered/sorted by the caller). */
    rows: Row[]
    columns: ColumnDef<Row>[]
    getRowKey: (row: Row) => string
    sortField: string | null
    sortDirection: "asc" | "desc" | null
    onSort: (field: string) => void
    /** Per-field width overrides of the column's default `width`. */
    columnWidths?: Record<string, number>
    /** Called with the new pixel width while dragging a resizer. Omit to make columns fixed. */
    onResizeColumn?: (field: string, width: number) => void
    /** Per-row CSS class (e.g. to tint AI rows). */
    getRowClassName?: (row: Row) => string | undefined
    /** Per-row inline style (e.g. status background). */
    getRowStyle?: (row: Row) => CSSProperties | undefined
    emptyMessage?: string
}

/**
 * Generic sortable strings table. The caller owns filtering and sorting, and persists widths when `onResizeColumn` is given.
 * @param rows - Rows to display.
 * @param columns - Column definitions.
 * @param getRowKey - Stable row key accessor.
 * @param sortField - Sorted field, or null.
 * @param sortDirection - Sort direction, or null.
 * @param onSort - Header-click handler.
 * @param columnWidths - Per-field width overrides.
 * @param onResizeColumn - Resize handler. Omit to make columns fixed.
 * @param getRowClassName - Per-row class accessor.
 * @param getRowStyle - Per-row style accessor.
 * @param emptyMessage - Message shown when there are no rows.
 * @returns The table.
 */
export function StringsTable<Row>({
    rows,
    columns,
    getRowKey,
    sortField,
    sortDirection,
    onSort,
    columnWidths,
    onResizeColumn,
    getRowClassName,
    getRowStyle,
    emptyMessage = "No rows match the current filter.",
}: StringsTableProps<Row>) {
    const resizeRef = useRef<{ field: string; startX: number; startWidth: number } | null>(null)

    const sortIcon = (field: string) => {
        if (sortField !== field || !sortDirection) return <FaSort className="sort-icon" />
        return sortDirection === "asc" ? <FaSortUp className="sort-icon active" /> : <FaSortDown className="sort-icon active" />
    }

    const widthOf = (col: ColumnDef<Row>) => columnWidths?.[col.field] ?? col.width

    const onResizeStart = (e: ReactPointerEvent, col: ColumnDef<Row>) => {
        e.stopPropagation()
        e.preventDefault()
        resizeRef.current = { field: col.field, startX: e.clientX, startWidth: widthOf(col) }
        e.currentTarget.setPointerCapture?.(e.pointerId)
    }
    const onResizeMove = (e: ReactPointerEvent) => {
        if (!resizeRef.current) return
        const { field, startX, startWidth } = resizeRef.current
        onResizeColumn?.(field, Math.max(80, startWidth + (e.clientX - startX)))
    }
    const onResizeEnd = () => {
        resizeRef.current = null
    }

    return (
        <div className="glass-card string-table-container" style={{ maxHeight: "calc(100vh - 420px)", minHeight: "400px", overflow: "auto" }}>
            <table>
                <thead>
                    <tr>
                        {columns.map((col) => (
                            <th
                                key={col.field}
                                data-field={col.field}
                                className="sortable-th"
                                style={{ width: widthOf(col), position: "sticky", top: 0, zIndex: 10, background: "var(--bg-color)" }}
                                onClick={col.sortable ? () => onSort(col.field) : undefined}
                            >
                                {col.label}
                                {col.sortable && sortIcon(col.field)}
                                {onResizeColumn && <div className="resizer" onPointerDown={(e) => onResizeStart(e, col)} onPointerMove={onResizeMove} onPointerUp={onResizeEnd} />}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 ? (
                        <tr>
                            <td colSpan={columns.length} style={{ textAlign: "center", color: "var(--text-dim)", padding: "2rem" }}>
                                {emptyMessage}
                            </td>
                        </tr>
                    ) : (
                        rows.map((row) => (
                            <tr key={getRowKey(row)} className={getRowClassName?.(row)} style={getRowStyle?.(row)}>
                                {columns.map((col) => (
                                    <td key={col.field} className={col.cellClassName}>
                                        {col.render(row)}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    )
}
