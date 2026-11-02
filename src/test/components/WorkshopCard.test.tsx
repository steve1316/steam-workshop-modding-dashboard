import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import WorkshopCard from "@/components/WorkshopCard"

describe("WorkshopCard", () => {
    it("renders the title as an h3", () => {
        render(<WorkshopCard title="My Title" />)
        const heading = screen.getByRole("heading", { name: "My Title", level: 3 })
        expect(heading).toBeInTheDocument()
    })

    it("renders the preview image when previewImageUrl is provided", () => {
        render(<WorkshopCard title="t" previewImageUrl="/api/preview.png" previewAlt="alt-text" />)
        const img = screen.getByAltText("alt-text") as HTMLImageElement
        expect(img.src).toContain("/api/preview.png")
    })

    it("does not render the preview slot when previewImageUrl is null", () => {
        render(<WorkshopCard title="t" previewImageUrl={null} />)
        expect(screen.queryByRole("img")).not.toBeInTheDocument()
        expect(screen.queryByTestId("workshop-card-placeholder")).not.toBeInTheDocument()
    })

    it("does not render the preview slot when previewImageUrl is omitted", () => {
        render(<WorkshopCard title="t" />)
        expect(screen.queryByRole("img")).not.toBeInTheDocument()
        expect(screen.queryByTestId("workshop-card-placeholder")).not.toBeInTheDocument()
    })

    it("swaps to the placeholder when the image fires onError", () => {
        render(<WorkshopCard title="t" previewImageUrl="/api/missing.png" previewAlt="alt-text" />)
        const img = screen.getByAltText("alt-text")
        fireEvent.error(img)
        expect(screen.queryByRole("img")).not.toBeInTheDocument()
        expect(screen.getByTestId("workshop-card-placeholder")).toBeInTheDocument()
    })

    it("renders the idBadge when provided", () => {
        const { container } = render(<WorkshopCard title="t" idBadge="1234567890" />)
        const badge = container.querySelector(".id-badge")
        expect(badge?.textContent).toBe("1234567890")
    })

    it("renders the subtitle when provided", () => {
        render(<WorkshopCard title="t" subtitle={<span>by Nanu</span>} />)
        expect(screen.getByText("by Nanu")).toBeInTheDocument()
    })

    it("renders children in the slot below the header", () => {
        render(
            <WorkshopCard title="t">
                <button>Slot button</button>
            </WorkshopCard>
        )
        expect(screen.getByRole("button", { name: "Slot button" })).toBeInTheDocument()
    })

    it("forwards arbitrary HTML attributes to the root element", () => {
        const { container } = render(<WorkshopCard title="t" data-mod-id="abc" />)
        expect(container.firstChild).toHaveAttribute("data-mod-id", "abc")
    })
})
