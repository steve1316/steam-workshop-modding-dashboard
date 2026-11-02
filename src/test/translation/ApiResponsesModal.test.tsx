import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ApiResponsesModal, type ApiResponseEntry } from "@/components/ApiResponsesModal"

const ENTRIES: ApiResponseEntry[] = [
    { id: "a", kind: "translate-batch", timestamp: "2026-05-25T00:00:00Z", model: "claude", inputTokens: 10, outputTokens: 20, costUsd: 0.01, keysOrInputs: ["k1", "k2"], rawText: "RAW A" },
    { id: "b", model: "claude", inputTokens: null, outputTokens: null, costUsd: 0.02, rawText: "RAW B" },
]

describe("shared ApiResponsesModal", () => {
    it("lists one tab per entry and shows the first entry's raw response + total cost", () => {
        render(<ApiResponsesModal entries={ENTRIES} onClose={vi.fn()} />)
        expect(screen.getAllByTestId("api-response-tab")).toHaveLength(2)
        expect(screen.getByText("RAW A")).toBeInTheDocument()
        // Total cost across entries: 0.01 + 0.02 = 0.03
        expect(screen.getByText(/\$0\.0300/)).toBeInTheDocument()
    })

    it("switches detail when another tab is clicked", () => {
        render(<ApiResponsesModal entries={ENTRIES} onClose={vi.fn()} />)
        fireEvent.click(screen.getAllByTestId("api-response-tab")[1])
        expect(screen.getByText("RAW B")).toBeInTheDocument()
    })

    it("shows an empty state when there are no entries", () => {
        render(<ApiResponsesModal entries={[]} onClose={vi.fn()} />)
        expect(screen.getByText(/No API responses recorded yet/i)).toBeInTheDocument()
    })

    it("falls back to a Batch label when an entry has no kind", () => {
        render(<ApiResponsesModal entries={[ENTRIES[1]]} onClose={vi.fn()} />)
        expect(screen.getByText("Batch 1")).toBeInTheDocument()
    })
})
