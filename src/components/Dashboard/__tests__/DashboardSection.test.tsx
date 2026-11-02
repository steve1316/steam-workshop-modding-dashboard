import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import DashboardSection from "@/components/Dashboard/DashboardSection"

describe("DashboardSection", () => {
    it("shows the titled skeleton while loading", () => {
        render(
            <DashboardSection title="Translation Mods" loading skeletonCount={3} skeletonLabel="Loading translation mods" empty={false} emptyMessage="None">
                <p>cards</p>
            </DashboardSection>
        )
        expect(screen.getByRole("heading", { level: 2, name: "Translation Mods" })).toBeInTheDocument()
        expect(screen.getByRole("status", { name: "Loading translation mods" })).toBeInTheDocument()
        expect(screen.queryByText("cards")).not.toBeInTheDocument()
    })

    it("shows the error with a Retry button in place of the skeleton", async () => {
        const onRetry = vi.fn()
        render(
            <DashboardSection loading error="Could not load mods: HTTP 500" onRetry={onRetry} empty={false} emptyMessage="None">
                <p>cards</p>
            </DashboardSection>
        )
        expect(screen.getByRole("alert")).toHaveTextContent("Could not load mods: HTTP 500")
        expect(screen.queryByRole("status")).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it("shows the empty message when there is nothing to list", () => {
        render(
            <DashboardSection loading={false} empty emptyMessage={'No mods match "zzz".'}>
                <p>cards</p>
            </DashboardSection>
        )
        expect(screen.getByText('No mods match "zzz".')).toBeInTheDocument()
        expect(screen.queryByText("cards")).not.toBeInTheDocument()
    })

    it("renders its children once loaded, with no heading when untitled", () => {
        render(
            <DashboardSection loading={false} empty={false} emptyMessage="None">
                <p>cards</p>
            </DashboardSection>
        )
        expect(screen.getByText("cards")).toBeInTheDocument()
        expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    })
})
