import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { TranslationToolbar } from "@/translation/TranslationToolbar"

describe("TranslationToolbar", () => {
    it("renders the actions in CA's order, in three groups", () => {
        const click = { onClick: vi.fn() }
        const { container } = render(
            <TranslationToolbar
                glossary={{ ...click, count: 26 }}
                suggestions={{ ...click, count: 3 }}
                scan={{ ...click, scanning: false }}
                apiResponses={click}
                context={{ ...click, label: "Character Context", hasContext: true }}
                history={click}
                reset={click}
                clearEnglish={click}
                extraActions={<button>Translate Names</button>}
                translate={<button>Translate (Claude)</button>}
                sync={<button>Sync Changes</button>}
            />
        )
        const groups = container.querySelectorAll(".mod-actions-group")
        expect(groups).toHaveLength(3)
        const names = (g: Element) => [...g.querySelectorAll("button")].map((b) => b.textContent?.trim())
        expect(names(groups[0])).toEqual(["Mod Glossary (26)", "Suggestions3", "Scan for Terms", "API Responses", "Character Context"])
        expect(names(groups[1])).toEqual(["History", "Reset", "Clear English"])
        expect(names(groups[2])).toEqual(["Translate Names", "Translate (Claude)", "Sync Changes"])
    })

    it("hides omitted actions and a zero Suggestions count", () => {
        render(<TranslationToolbar glossary={{ count: 0, onClick: vi.fn() }} suggestions={{ count: 0, onClick: vi.fn() }} />)
        expect(screen.getByRole("button", { name: /Mod Glossary/ })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Suggestions/ })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /History/ })).not.toBeInTheDocument()
    })

    it("shows the scanning label, the count badge and the context dot", async () => {
        const onScan = vi.fn()
        const { container } = render(
            <TranslationToolbar suggestions={{ count: 2, onClick: vi.fn() }} scan={{ scanning: true, onClick: onScan }} context={{ label: "Mod Context", hasContext: true, onClick: vi.fn() }} />
        )
        expect(screen.getByRole("button", { name: "Scanning..." })).toBeDisabled()
        expect(container.querySelector(".btn-badge")).toHaveTextContent("2")
        expect(screen.getByRole("button", { name: "Mod Context" }).querySelector(".btn-dot")).not.toBeNull()
        await userEvent.click(screen.getByRole("button", { name: "Mod Context" }))
    })
})
