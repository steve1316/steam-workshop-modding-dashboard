import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import ValidationPanel from "@/games/total_war_warhammer_3/components/ValidationPanel"
import type { ValidationIssue } from "@/games/total_war_warhammer_3/lib/registryApi"

const EFFECT_ISSUE: ValidationIssue = {
    kind: "missing_effect_category",
    severity: "error",
    mod_package_name: "mod_a",
    mod_name: "Mod A",
    target: "melee_general",
    message: "modified_attributes references 'melee_general' but no such category exists in SUPPORTED_EFFECTS",
}

const PATH_ISSUE: ValidationIssue = {
    kind: "missing_mod_path",
    severity: "error",
    mod_package_name: "mod_b",
    mod_name: "Mod B",
    target: "/fake/mod_b.pack",
    message: "path '/fake/mod_b.pack' does not exist on disk",
}

describe("ValidationPanel", () => {
    it("renders nothing while issues are still loading", () => {
        const { container } = render(<ValidationPanel issues={null} onRefresh={vi.fn()} />)
        expect(container).toBeEmptyDOMElement()
    })

    it("renders nothing when there are no issues", () => {
        const { container } = render(<ValidationPanel issues={[]} onRefresh={vi.fn()} />)
        expect(container).toBeEmptyDOMElement()
    })

    it("shows the total issue count", () => {
        render(<ValidationPanel issues={[EFFECT_ISSUE, PATH_ISSUE]} onRefresh={vi.fn()} />)
        expect(screen.getByText(/2 issues/i)).toBeInTheDocument()
    })

    it("expands missing mod paths and collapses missing effect categories by default", () => {
        render(<ValidationPanel issues={[EFFECT_ISSUE, PATH_ISSUE]} onRefresh={vi.fn()} />)
        const paths = screen.getByText(/missing mod paths \(1\)/i).closest("details")
        const effects = screen.getByText(/missing effect categories \(1\)/i).closest("details")
        expect(paths).toHaveAttribute("open")
        expect(effects).not.toHaveAttribute("open")
    })

    it("omits a group that has no issues", () => {
        render(<ValidationPanel issues={[PATH_ISSUE]} onRefresh={vi.fn()} />)
        expect(screen.queryByText(/missing effect categories/i)).not.toBeInTheDocument()
        expect(screen.getByText("Mod B")).toBeInTheDocument()
        expect(screen.getByText(PATH_ISSUE.target)).toBeInTheDocument()
    })

    it("calls onRefresh and shows a busy label until it resolves", async () => {
        let resolve: () => void = () => {}
        const onRefresh = vi.fn(() => new Promise<void>((r) => (resolve = r)))
        render(<ValidationPanel issues={[PATH_ISSUE]} onRefresh={onRefresh} />)
        await userEvent.click(screen.getByRole("button", { name: /refresh/i }))
        expect(onRefresh).toHaveBeenCalledTimes(1)
        expect(screen.getByRole("button", { name: /refreshing/i })).toBeDisabled()
        resolve()
        expect(await screen.findByRole("button", { name: /^refresh$/i })).toBeEnabled()
    })
})
