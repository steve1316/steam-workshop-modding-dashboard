import { useCallback, useEffect, useMemo, useState } from "react"

export type SortDirection = "asc" | "desc" | null

/** Options for `useTableView`. Pass module-level functions for `select` and `sortRows` so the visible rows are not recomputed every render. */
interface TableViewOptions<Row, Field extends string, Filter extends string> {
    rows: Row[]
    /** localStorage key the column widths are kept under. */
    storageKey: string
    defaultWidths: Record<Field, number>
    /** Starting sort. A null direction keeps the rows in the order given. */
    initialSort: { key: Field; direction: SortDirection }
    /** Narrow the rows to the active status filter and search text. */
    select: (rows: Row[], filter: Filter | "all", search: string) => Row[]
    sortRows: (rows: Row[], key: Field, direction: "asc" | "desc") => Row[]
}

/**
 * Read saved column widths, filling any missing column from the defaults.
 *
 * @param storageKey The localStorage key.
 * @param defaults Width per column.
 * @returns The widths to start from.
 */
function readWidths<Field extends string>(storageKey: string, defaults: Record<Field, number>): Record<Field, number> {
    try {
        const raw = window.localStorage.getItem(storageKey)
        if (raw) return { ...defaults, ...(JSON.parse(raw) as Partial<Record<Field, number>>) }
    } catch {
        // Unreadable storage or a corrupt value falls back to the defaults.
    }
    return defaults
}

/**
 * Status filter, search, sort and column widths for a translation table. Sort cycles asc, desc, then off, and widths persist across visits.
 *
 * @param options Rows, storage key, defaults, and the filter and sort functions.
 * @returns The current filter and search, and `viewProps` to spread into `<TranslationPage>`.
 */
export function useTableView<Row, Field extends string, Filter extends string>(options: TableViewOptions<Row, Field, Filter>) {
    const { rows, storageKey, defaultWidths, initialSort, select, sortRows } = options
    const [filter, setFilter] = useState<Filter | "all">("all")
    const [search, setSearch] = useState("")
    const [sort, setSort] = useState(initialSort)
    const [columnWidths, setColumnWidths] = useState(() => readWidths(storageKey, defaultWidths))

    useEffect(() => {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify(columnWidths))
        } catch {
            // A full or blocked storage only costs the widths on the next visit.
        }
    }, [storageKey, columnWidths])

    const onSort = useCallback((field: string) => {
        const key = field as Field
        setSort((prev) => {
            if (prev.key !== key || prev.direction === null) return { key, direction: "asc" }
            return { key, direction: prev.direction === "asc" ? "desc" : null }
        })
    }, [])

    const onResizeColumn = useCallback((field: string, width: number) => setColumnWidths((prev) => ({ ...prev, [field]: width })), [])

    const visibleRows = useMemo(() => {
        const picked = select(rows, filter, search)
        return sort.direction ? sortRows(picked, sort.key, sort.direction) : picked
    }, [rows, filter, search, sort, select, sortRows])

    return {
        filter,
        search,
        viewProps: {
            activeFilter: filter,
            onFilterChange: (value: string) => setFilter(value as Filter | "all"),
            search,
            onSearchChange: setSearch,
            rows: visibleRows,
            sortField: sort.direction ? sort.key : null,
            sortDirection: sort.direction,
            onSort,
            columnWidths: columnWidths as Record<string, number>,
            onResizeColumn,
        },
    }
}
