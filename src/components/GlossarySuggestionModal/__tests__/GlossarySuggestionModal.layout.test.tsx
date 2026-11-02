import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import GlossarySuggestionModal from "@/components/GlossarySuggestionModal"
import type { TermSuggestion } from "@/lib/types"

const LONG = "A".repeat(400)
const SUGGESTIONS: TermSuggestion[] = [{ english: LONG, source: "原".repeat(200), source_lang: "Chinese", category: "unit", reason: "long term" }]

describe("GlossarySuggestionModal layout", () => {
    it("keeps the term-details column shrinkable so the action buttons stay in-bounds", () => {
        render(<GlossarySuggestionModal gameId="chrono_ark" modId="1" suggestions={SUGGESTIONS} onClose={vi.fn()} onUpdated={vi.fn()} />)
        // The per-term Accept button must render (proves the row built), and the details column must carry the shrink guard.
        expect(screen.getByRole("button", { name: /Accept$/i })).toBeInTheDocument()
        const details = document.querySelector('[data-testid="suggestion-details"]') as HTMLElement
        expect(details).not.toBeNull()
        expect(details.style.minWidth).toBe("0px")
        expect(details.style.flex).toContain("1")
    })
})
