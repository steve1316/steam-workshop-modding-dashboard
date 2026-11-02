import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import DashboardHeader from "@/components/Dashboard/DashboardHeader"
import { progressLabel } from "@/lib/progressLabel"

describe("DashboardHeader", () => {
    it("renders the title, tagline, and one toolbar row holding the search field and the actions", () => {
        render(
            <DashboardHeader
                title="Workshop Dashboard"
                tagline="Manage and translate your Chrono Ark mods"
                search=""
                onSearchChange={vi.fn()}
                searchPlaceholder="Search by name or author..."
                actions={<button>Refresh</button>}
            />
        )
        expect(screen.getByRole("heading", { level: 1, name: "Workshop Dashboard" })).toBeInTheDocument()
        expect(screen.getByText("Manage and translate your Chrono Ark mods")).toBeInTheDocument()
        const toolbar = screen.getByPlaceholderText("Search by name or author...").closest(".dashboard-toolbar")
        expect(toolbar).toContainElement(screen.getByRole("button", { name: "Refresh" }))
    })

    it("sizes the search field to the card width, falling back to 320px before a card has rendered", () => {
        const props = { title: "T", tagline: "t", search: "", onSearchChange: vi.fn(), searchPlaceholder: "Search" }
        const { container, rerender } = render(<DashboardHeader {...props} searchWidth={287} />)
        expect(container.querySelector(".search-input")).toHaveStyle({ width: "287px" })
        rerender(<DashboardHeader {...props} />)
        expect(container.querySelector(".search-input")).toHaveStyle({ width: "320px" })
    })

    it("reports typing through onSearchChange", async () => {
        const onSearchChange = vi.fn()
        render(<DashboardHeader title="T" tagline="t" search="" onSearchChange={onSearchChange} searchPlaceholder="Search" />)
        await userEvent.type(screen.getByPlaceholderText("Search"), "R")
        expect(onSearchChange).toHaveBeenCalledWith("R")
    })
})

describe("progressLabel", () => {
    it("shows the idle label, then the verb, then the verb with a count", () => {
        expect(progressLabel("Refresh", "Refreshing", false, null)).toBe("Refresh")
        expect(progressLabel("Refresh", "Refreshing", true, null)).toBe("Refreshing\u2026")
        expect(progressLabel("Refresh", "Refreshing", true, { current: 3, total: 5 })).toBe("Refreshing (3/5)\u2026")
    })

    it("ignores stale progress once the task is idle", () => {
        expect(progressLabel("Refresh", "Refreshing", false, { current: 5, total: 5 })).toBe("Refresh")
    })
})
