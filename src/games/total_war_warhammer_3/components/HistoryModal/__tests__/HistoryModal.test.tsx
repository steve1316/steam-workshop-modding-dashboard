import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import HistoryModal from "@/games/total_war_warhammer_3/components/HistoryModal"
import type { HistoryEntry } from "@/lib/types"

const SNAPS: HistoryEntry[] = [
    { id: "01J", created_at: "2026-05-25T01:00:00Z", reason: "pre-clear-translations", kind: "auto", files: [] },
    { id: "01H", created_at: "2026-05-25T00:00:00Z", reason: "manual save", kind: "manual", files: [] },
]

function mockJson(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })
}

beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJson(SNAPS))
})

afterEach(() => {
    vi.restoreAllMocks()
})

describe("HistoryModal", () => {
    it("lists snapshots newest first", async () => {
        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={vi.fn()} />)
        await waitFor(() => screen.getByText(/pre-clear-translations/))
        const rows = screen.getAllByTestId("snapshot-row")
        expect(rows[0]).toHaveTextContent("pre-clear-translations")
        expect(rows[1]).toHaveTextContent("manual save")
    })

    it("shows kind badges", async () => {
        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={vi.fn()} />)
        await waitFor(() => screen.getByText("auto"))
        expect(screen.getByText("manual")).toBeInTheDocument()
    })

    it("saves a manual snapshot when Save is clicked", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(SNAPS)) // initial GET
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "saved", id: "01K" })) // POST
        fetchSpy.mockResolvedValueOnce(mockJson([{ id: "01K", created_at: "2026-05-25T02:00:00Z", reason: "my save", kind: "manual", files: [] }, ...SNAPS])) // refresh GET

        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={vi.fn()} />)
        await waitFor(() => screen.getByText(/pre-clear-translations/))

        fireEvent.change(screen.getByPlaceholderText(/Snapshot label/i), { target: { value: "my save" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Save snapshot/i }))
        })
        await waitFor(() => expect(screen.getByText("my save")).toBeInTheDocument())
    })

    it("calls onRestored after restoring a snapshot", async () => {
        const onRestored = vi.fn()
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(SNAPS)) // initial GET
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok" })) // POST restore

        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={onRestored} />)
        await waitFor(() => screen.getByText(/pre-clear-translations/))

        const restoreButtons = screen.getAllByRole("button", { name: /Restore/i })
        await act(async () => {
            fireEvent.click(restoreButtons[0])
        })
        await act(async () => {
            fireEvent.click(within(await screen.findByRole("dialog", { name: "Restore snapshot" })).getByRole("button", { name: "Restore" }))
        })
        await waitFor(() => expect(onRestored).toHaveBeenCalled())
    })

    it("deletes a snapshot row after confirmation", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(SNAPS)) // initial GET
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok" })) // DELETE
        fetchSpy.mockResolvedValueOnce(mockJson([SNAPS[1]])) // refresh GET

        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={vi.fn()} />)
        await waitFor(() => screen.getByText(/pre-clear-translations/))

        const deleteButtons = screen.getAllByRole("button", { name: /Delete/i })
        await act(async () => {
            fireEvent.click(deleteButtons[0])
        })
        await act(async () => {
            fireEvent.click(await screen.findByRole("button", { name: "Delete snapshot" }))
        })
        await waitFor(() => expect(screen.queryByText(/pre-clear-translations/)).not.toBeInTheDocument())
    })

    it("shows load errors inside the dialog instead of an alert", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(mockJson({ detail: "snapshots unavailable" }, 500))
        const alertSpy = vi.spyOn(window, "alert")
        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode={false} onRestored={vi.fn()} />)
        expect(await screen.findByText(/snapshots unavailable|500/)).toBeInTheDocument()
        expect(alertSpy).not.toHaveBeenCalled()
    })

    it("shows a restore-focused header when defaultRestoreMode is true", async () => {
        render(<HistoryModal workshopId="123" onClose={vi.fn()} defaultRestoreMode onRestored={vi.fn()} />)
        await waitFor(() => screen.getByText(/Reset to snapshot/i))
    })
})
