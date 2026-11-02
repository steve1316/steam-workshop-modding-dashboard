import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import ErrorBoundary from "@/components/ui/ErrorBoundary"

/**
 * A child that always throws while rendering.
 *
 * @returns Never returns.
 */
function Crash(): never {
    throw new Error("Cannot read properties of undefined (reading 'filter')")
}

afterEach(() => vi.restoreAllMocks())

describe("ErrorBoundary", () => {
    it("shows an error state instead of a blank page when a child crashes", () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        render(
            <ErrorBoundary>
                <Crash />
            </ErrorBoundary>
        )
        expect(screen.getByRole("alert")).toHaveTextContent("Cannot read properties of undefined")
        expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument()
    })

    it("recovers when remounted with a new key, as App does on navigation", () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        const { rerender } = render(
            <ErrorBoundary key="/a">
                <Crash />
            </ErrorBoundary>
        )
        rerender(
            <ErrorBoundary key="/b">
                <p>next page</p>
            </ErrorBoundary>
        )
        expect(screen.getByText("next page")).toBeInTheDocument()
    })
})
