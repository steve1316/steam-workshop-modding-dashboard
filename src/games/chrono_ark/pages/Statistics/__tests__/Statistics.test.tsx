import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import StatisticsPage from "@/games/chrono_ark/pages/Statistics"

const STATS = { tm_entries: 11279, tm_hits: 3, total_mods: 97, global_progress: 100.0, total_strings: 15583 }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

afterEach(() => {
    vi.restoreAllMocks()
})

describe("Chrono Ark StatisticsPage", () => {
    it("shows a loading state while the statistics load", () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => {}))
        render(<StatisticsPage />)
        expect(screen.getByText("Loading statistics...")).toBeInTheDocument()
        expect(screen.queryByText("No statistics available.")).not.toBeInTheDocument()
    })

    it("renders the three statistic tiles", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(json(STATS)))
        render(<StatisticsPage />)
        expect(await screen.findByText("100%")).toBeInTheDocument()
        expect(screen.getByText("11279")).toBeInTheDocument()
        expect(screen.getByText("3")).toBeInTheDocument()
        expect(screen.getByText("Translation Memory Entries").closest(".stat-tile")).not.toBeNull()
    })

    it("shows an error with Retry when the statistics fail to load, and Retry loads them", async () => {
        vi.spyOn(globalThis, "fetch")
            .mockImplementationOnce(() => Promise.resolve(json({ detail: "boom" }, 500)))
            .mockImplementation(() => Promise.resolve(json(STATS)))
        render(<StatisticsPage />)
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load statistics")
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("100%")).toBeInTheDocument()
    })
})
