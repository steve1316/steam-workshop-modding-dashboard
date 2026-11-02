import { render, screen, fireEvent } from "@testing-library/react"
import { StringsTable } from "@/translation/StringsTable"
import type { ColumnDef } from "@/translation/types"

interface Row {
    id: string
    name: string
}

const rows: Row[] = [
    { id: "1", name: "Alpha" },
    { id: "2", name: "Beta" },
]

const columns: ColumnDef<Row>[] = [{ field: "name", label: "Name", width: 200, sortable: true, render: (r) => r.name }]

describe("StringsTable", () => {
    it("renders a header and one row per item", () => {
        render(<StringsTable rows={rows} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={vi.fn()} />)
        expect(screen.getByText("Name")).toBeInTheDocument()
        expect(screen.getByText("Alpha")).toBeInTheDocument()
        expect(screen.getByText("Beta")).toBeInTheDocument()
    })

    it("calls onSort with the column field when a sortable header is clicked", () => {
        const onSort = vi.fn()
        render(<StringsTable rows={rows} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={onSort} />)
        fireEvent.click(screen.getByText("Name"))
        expect(onSort).toHaveBeenCalledWith("name")
    })

    it("shows the empty message when there are no rows", () => {
        render(<StringsTable rows={[]} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={vi.fn()} emptyMessage="No rows." />)
        expect(screen.getByText("No rows.")).toBeInTheDocument()
    })

    it("uses columnWidths overrides over the column default width", () => {
        const { container } = render(<StringsTable rows={rows} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={vi.fn()} columnWidths={{ name: 333 }} />)
        const th = container.querySelector("th") as HTMLElement
        expect(th.style.width).toBe("333px")
    })

    it("does not render resizer handles unless onResizeColumn is supplied", () => {
        const { container, rerender } = render(<StringsTable rows={rows} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={vi.fn()} />)
        expect(container.querySelector(".resizer")).toBeNull()
        rerender(<StringsTable rows={rows} columns={columns} getRowKey={(r) => r.id} sortField={null} sortDirection={null} onSort={vi.fn()} onResizeColumn={vi.fn()} />)
        expect(container.querySelector(".resizer")).not.toBeNull()
    })

    it("applies per-row class and style accessors", () => {
        const { container } = render(
            <StringsTable
                rows={rows}
                columns={columns}
                getRowKey={(r) => r.id}
                sortField={null}
                sortDirection={null}
                onSort={vi.fn()}
                getRowClassName={(r) => (r.id === "1" ? "row-highlight" : undefined)}
                getRowStyle={(r) => (r.id === "1" ? { background: "rgb(10, 20, 30)" } : undefined)}
            />
        )
        const firstRow = container.querySelectorAll("tbody tr")[0] as HTMLElement
        expect(firstRow.className).toBe("row-highlight")
        expect(firstRow.style.background).toBe("rgb(10, 20, 30)")
    })
})
