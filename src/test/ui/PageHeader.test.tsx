import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import PageHeader from "@/components/ui/PageHeader"

describe("PageHeader", () => {
    it("renders the title as the page heading with the adornments beside it, not inside it", () => {
        render(<PageHeader title="Whc's Cathay unit pack" adornments={<span>pending</span>} />)
        const heading = screen.getByRole("heading", { level: 1, name: "Whc's Cathay unit pack" })
        expect(heading).not.toContainElement(screen.getByText("pending"))
        expect(screen.getByText("pending").closest(".page-header-adornments")).not.toBeNull()
    })

    it("renders the back button only when onBack is given, and calls it", async () => {
        const onBack = vi.fn()
        const { rerender } = render(<PageHeader title="T" />)
        expect(screen.queryByRole("button", { name: /Back to Dashboard/ })).not.toBeInTheDocument()
        rerender(<PageHeader title="T" onBack={onBack} />)
        await userEvent.click(screen.getByRole("button", { name: /Back to Dashboard/ }))
        expect(onBack).toHaveBeenCalledTimes(1)
    })

    it("renders the leading image, subtitle, meta and actions", () => {
        render(<PageHeader title="Roland" image="http://example.test/p.png" imageAlt="Roland" subtitle="by Someone" meta={<p>152 / 152</p>} actions={<button>Sync</button>} />)
        expect(screen.getByRole("img", { name: "Roland" })).toHaveAttribute("src", "http://example.test/p.png")
        expect(screen.getByText("by Someone")).toBeInTheDocument()
        expect(screen.getByText("152 / 152")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Sync" }).closest(".mod-actions")).not.toBeNull()
    })

    it("uses the given class for the action row instead of the translation toolbar row", () => {
        render(<PageHeader title="Workshop Dashboard" actions={<button>Refresh</button>} actionsClassName="dashboard-toolbar" />)
        const button = screen.getByRole("button", { name: "Refresh" })
        expect(button.closest(".dashboard-toolbar")).not.toBeNull()
        expect(button.closest(".mod-actions")).toBeNull()
    })
})
