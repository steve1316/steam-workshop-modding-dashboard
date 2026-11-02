import { render, screen } from "@testing-library/react"
import { StatusBadge } from "@/translation/StatusBadge"

describe("StatusBadge", () => {
    it("renders the canonical label and CSS classes", () => {
        render(<StatusBadge status="pending" />)
        const badge = screen.getByText("PENDING")
        expect(badge).toHaveClass("status-badge")
        expect(badge).toHaveClass("status-translated")
    })

    it("shows the untranslatable reason as a tooltip", () => {
        render(<StatusBadge status="untranslatable" reason="machine code" />)
        expect(screen.getByText("N/A")).toHaveAttribute("title", "machine code")
    })

    it("has no tooltip for non-untranslatable statuses", () => {
        render(<StatusBadge status="synced" />)
        expect(screen.getByText("SYNCED")).not.toHaveAttribute("title")
    })
})
