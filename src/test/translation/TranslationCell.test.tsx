import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TranslationCell } from "@/components/TranslationPage/TranslationCell"

describe("TranslationCell", () => {
    it("shows the previous translation struck through when it differs from the current value", () => {
        render(<TranslationCell value="New" previous="Old" synced={false} onSave={vi.fn()} />)
        const prev = screen.getByText("Old")
        expect(prev).toBeInTheDocument()
        expect(prev.className).toContain("prev-translation")
    })

    it("omits the strikethrough when previous equals current or is empty", () => {
        render(<TranslationCell value="Same" previous="Same" synced={false} onSave={vi.fn()} />)
        expect(screen.queryByText((_, el) => el?.className.includes("prev-translation") ?? false)).toBeNull()
    })

    it("renders the untranslatable reason instead of an editor when given one", () => {
        render(<TranslationCell value="" previous="" synced={false} untranslatableReason="binary asset" onSave={vi.fn()} />)
        expect(screen.getByText("binary asset")).toBeInTheDocument()
    })

    it("highlights the search query in the displayed translation", () => {
        const { container } = render(<TranslationCell value="Summon a dragon" synced={false} highlight="DRAGON" onSave={vi.fn()} />)
        expect(container.querySelector("mark.search-highlight")?.textContent).toBe("dragon")
    })
})
