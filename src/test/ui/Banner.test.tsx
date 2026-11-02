import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import Banner from "@/ui/Banner"

describe("Banner", () => {
    it("renders its content with the tone class", () => {
        render(<Banner tone="warning">Heads up</Banner>)
        expect(screen.getByText("Heads up").closest(".banner")).toHaveClass("banner-warning")
    })

    it("renders a Dismiss button only when onDismiss is given", () => {
        const onDismiss = vi.fn()
        const { rerender } = render(<Banner tone="info">x</Banner>)
        expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument()
        rerender(
            <Banner tone="info" onDismiss={onDismiss}>
                x
            </Banner>
        )
        fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
        expect(onDismiss).toHaveBeenCalledTimes(1)
    })
})
