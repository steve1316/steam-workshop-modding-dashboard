import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ApiResponsesModal from "@/games/total_war_warhammer_3/components/ApiResponsesModal"
import type { ApiLogEntry } from "@/lib/types"

const ENTRIES: ApiLogEntry[] = [
    {
        timestamp: "2026-05-25T01:00:00Z",
        kind: "translate-batch",
        provider: "claude",
        model: "claude",
        input_tokens: null,
        output_tokens: null,
        cost_usd: null,
        keys_or_inputs: ["k1", "k2"],
        raw_response: '{"k1":"Hello"}',
    },
    {
        timestamp: "2026-05-25T00:00:00Z",
        kind: "scan-terms",
        provider: "claude",
        model: "claude",
        input_tokens: null,
        output_tokens: null,
        cost_usd: null,
        keys_or_inputs: [],
        raw_response: "[]",
    },
]

function mockJson(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status })
}

beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJson(ENTRIES))
})

afterEach(() => {
    vi.restoreAllMocks()
})

describe("ApiResponsesModal", () => {
    it("renders entry rows newest first", async () => {
        render(<ApiResponsesModal workshopId="123" onClose={vi.fn()} />)
        await waitFor(() => screen.getByText(/translate-batch/))
        const tabs = screen.getAllByTestId("api-response-tab")
        expect(tabs[0]).toHaveTextContent(/translate-batch/)
        expect(tabs[1]).toHaveTextContent(/scan-terms/)
    })

    it("shows the first entry's raw response by default", async () => {
        render(<ApiResponsesModal workshopId="123" onClose={vi.fn()} />)
        await waitFor(() => screen.getByText(/"k1":"Hello"/))
    })

    it("switches active entry when a sidebar row is clicked", async () => {
        render(<ApiResponsesModal workshopId="123" onClose={vi.fn()} />)
        await waitFor(() => screen.getByText(/"k1":"Hello"/))
        fireEvent.click(screen.getAllByTestId("api-response-tab")[1])
        await waitFor(() => expect(screen.queryByText(/"k1":"Hello"/)).not.toBeInTheDocument())
        expect(screen.getByText("[]")).toBeInTheDocument()
    })

    it("renders empty state when no entries", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJson([]))
        render(<ApiResponsesModal workshopId="123" onClose={vi.fn()} />)
        await waitFor(() => screen.getByText(/No API responses recorded yet/i))
    })
})
