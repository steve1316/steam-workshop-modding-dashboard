import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import ValidationBadge from "@/games/total_war_warhammer_3/components/ValidationBadge"
import type { ValidationIssue } from "@/games/total_war_warhammer_3/lib/types"

function makeIssue(overrides: Partial<ValidationIssue> = {}): ValidationIssue {
    return {
        kind: "missing_effect_category",
        severity: "error",
        mod_package_name: "test_mod",
        mod_name: "Test Mod",
        target: "melee",
        message: "modified_attributes references 'melee' but no such category exists",
        ...overrides,
    }
}

describe("ValidationBadge", () => {
    it("renders amber warning icon when issues are non-empty", () => {
        render(<ValidationBadge issues={[makeIssue()]} />)
        const badge = screen.getByLabelText(/validation issue/i)
        expect(badge).toBeInTheDocument()
    })

    it("does not render when issues array is empty", () => {
        const { container } = render(<ValidationBadge issues={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it("tooltip text contains every issue's message", () => {
        const issues = [makeIssue({ message: "first message" }), makeIssue({ message: "second message" })]
        render(<ValidationBadge issues={issues} />)
        const badge = screen.getByLabelText(/validation issue/i)
        expect(badge).toHaveAttribute("title", expect.stringContaining("first message"))
        expect(badge).toHaveAttribute("title", expect.stringContaining("second message"))
    })

    it("aria-label uses singular for one issue and plural for many", () => {
        const { rerender } = render(<ValidationBadge issues={[makeIssue()]} />)
        expect(screen.getByLabelText("1 validation issue")).toBeInTheDocument()

        rerender(<ValidationBadge issues={[makeIssue(), makeIssue()]} />)
        expect(screen.getByLabelText("2 validation issues")).toBeInTheDocument()
    })
})
