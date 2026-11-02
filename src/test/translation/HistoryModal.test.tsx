import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import HistoryModal, { type HistoryModalEntry } from "@/translation/HistoryModal"

const ENTRIES: HistoryModalEntry[] = [
    { id: "a", title: "Before reset", kind: "auto", createdAt: "2026-05-25T01:00:00Z", subtitle: <span>10 / 20 strings translated</span> },
    { id: "b", title: "My checkpoint", kind: "manual", createdAt: "2026-05-25T00:00:00Z" },
]

describe("shared HistoryModal", () => {
    it("renders entries with kind pills, titles, and an optional subtitle", () => {
        render(<HistoryModal entries={ENTRIES} onSave={vi.fn()} onRestore={vi.fn()} onDelete={vi.fn()} onClose={vi.fn()} />)
        expect(screen.getByText("Before reset")).toBeInTheDocument()
        expect(screen.getByText("My checkpoint")).toBeInTheDocument()
        expect(screen.getByText("auto")).toBeInTheDocument()
        expect(screen.getByText("manual")).toBeInTheDocument()
        expect(screen.getByText("10 / 20 strings translated")).toBeInTheDocument()
        expect(screen.getAllByTestId("snapshot-row")).toHaveLength(2)
    })

    it("shows the empty message when there are no entries", () => {
        render(<HistoryModal entries={[]} onSave={vi.fn()} onRestore={vi.fn()} onDelete={vi.fn()} onClose={vi.fn()} emptyMessage="No snapshots yet." />)
        expect(screen.getByText("No snapshots yet.")).toBeInTheDocument()
    })

    it("saves with the typed label and clears the input", async () => {
        const onSave = vi.fn().mockResolvedValue(undefined)
        render(<HistoryModal entries={ENTRIES} onSave={onSave} onRestore={vi.fn()} onDelete={vi.fn()} onClose={vi.fn()} />)
        const input = screen.getByPlaceholderText(/Snapshot label/i) as HTMLInputElement
        fireEvent.change(input, { target: { value: "checkpoint 1" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Save snapshot/i }))
        })
        expect(onSave).toHaveBeenCalledWith("checkpoint 1")
        await waitFor(() => expect(input.value).toBe(""))
    })

    it("surfaces a save error and keeps the label", async () => {
        const onSave = vi.fn().mockRejectedValue(new Error("boom"))
        render(<HistoryModal entries={ENTRIES} onSave={onSave} onRestore={vi.fn()} onDelete={vi.fn()} onClose={vi.fn()} />)
        const input = screen.getByPlaceholderText(/Snapshot label/i) as HTMLInputElement
        fireEvent.change(input, { target: { value: "keep me" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Save snapshot/i }))
        })
        await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument())
        expect(input.value).toBe("keep me")
    })

    it("invokes onRestore and onDelete with the clicked entry", () => {
        const onRestore = vi.fn()
        const onDelete = vi.fn()
        render(<HistoryModal entries={ENTRIES} onSave={vi.fn()} onRestore={onRestore} onDelete={onDelete} onClose={vi.fn()} />)
        fireEvent.click(screen.getAllByRole("button", { name: /Restore/i })[0])
        fireEvent.click(screen.getAllByRole("button", { name: /Delete/i })[0])
        expect(onRestore).toHaveBeenCalledWith(ENTRIES[0])
        expect(onDelete).toHaveBeenCalledWith(ENTRIES[0])
    })
})
