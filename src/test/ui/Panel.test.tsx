import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import Panel from "@/components/ui/Panel"

describe("Panel", () => {
    it("renders the title as an h3 directly followed by the help line, then the body", () => {
        render(
            <Panel title="Mod Context" help="Included in the translation prompt.">
                <button>Save Context</button>
            </Panel>
        )
        const heading = screen.getByRole("heading", { level: 3, name: "Mod Context" })
        expect(heading.nextElementSibling).toHaveTextContent("Included in the translation prompt.")
        expect(heading.nextElementSibling).toHaveClass("help-text")
        expect(screen.getByRole("button", { name: "Save Context" })).toBeInTheDocument()
    })

    it("is a static glass card that also takes the caller's class", () => {
        const { container } = render(<Panel className="context-panel">body</Panel>)
        expect(container.firstElementChild).toHaveClass("glass-card", "static", "panel", "context-panel")
    })

    it("skips the heading and help line when they are not given", () => {
        const { container } = render(<Panel>body</Panel>)
        expect(screen.queryByRole("heading")).not.toBeInTheDocument()
        expect(container.querySelector(".panel-help")).toBeNull()
    })

    it("renders as a fieldset whose legend names the group", () => {
        render(
            <Panel as="fieldset" title="Basics">
                <input aria-label="Name" />
            </Panel>
        )
        const group = screen.getByRole("group", { name: "Basics" })
        expect(group.tagName).toBe("FIELDSET")
        expect(group).toHaveClass("glass-card", "static", "panel")
        expect(group).toContainElement(screen.getByRole("textbox", { name: "Name" }))
    })
})
