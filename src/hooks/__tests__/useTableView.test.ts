import { act, renderHook } from "@/testUtils"
import { afterEach, describe, expect, it } from "vitest"

import { useTableView } from "@/hooks/useTableView"

type Row = { key: string; status: string }
type Field = "key" | "status"

const ROWS: Row[] = [
    { key: "b", status: "missing" },
    { key: "a", status: "synced" },
    { key: "c", status: "missing" },
]

const select = (rows: Row[], filter: string, search: string) => rows.filter((r) => (filter === "all" || r.status === filter) && r.key.includes(search))
const sortRows = (rows: Row[], key: Field, direction: "asc" | "desc") => [...rows].sort((a, b) => a[key].localeCompare(b[key]) * (direction === "asc" ? 1 : -1))

const options = { rows: ROWS, storageKey: "test-widths", defaultWidths: { key: 200, status: 120 }, initialSort: { key: "key" as Field, direction: null }, select, sortRows }

afterEach(() => {
    window.localStorage.clear()
})

describe("useTableView", () => {
    it("cycles a column's sort asc, desc, then off", () => {
        const { result } = renderHook(() => useTableView<Row, Field, string>(options))
        const keys = () => result.current.viewProps.rows.map((r) => r.key)
        expect(keys()).toEqual(["b", "a", "c"])
        act(() => result.current.viewProps.onSort("key"))
        expect(keys()).toEqual(["a", "b", "c"])
        act(() => result.current.viewProps.onSort("key"))
        expect(keys()).toEqual(["c", "b", "a"])
        act(() => result.current.viewProps.onSort("key"))
        expect(keys()).toEqual(["b", "a", "c"])
        expect(result.current.viewProps.sortField).toBeNull()
    })

    it("applies the status filter and search", () => {
        const { result } = renderHook(() => useTableView<Row, Field, string>(options))
        act(() => result.current.viewProps.onFilterChange("missing"))
        act(() => result.current.viewProps.onSearchChange("c"))
        expect(result.current.viewProps.rows).toEqual([{ key: "c", status: "missing" }])
        expect(result.current.search).toBe("c")
    })

    it("keeps resized column widths for the next mount", () => {
        const first = renderHook(() => useTableView<Row, Field, string>(options))
        act(() => first.result.current.viewProps.onResizeColumn("key", 321))
        first.unmount()
        const { result } = renderHook(() => useTableView<Row, Field, string>(options))
        expect(result.current.viewProps.columnWidths).toEqual({ key: 321, status: 120 })
    })
})
