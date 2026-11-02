import { render } from "@/testUtils"
import { describe, expect, it } from "vitest"

import HighlightText from "@/components/ui/HighlightText"

describe("HighlightText", () => {
    it("wraps every case-insensitive match in a mark", () => {
        const { container } = render(<HighlightText text="Fire and fireball" query="fire" />)
        const marks = [...container.querySelectorAll("mark.search-highlight")].map((m) => m.textContent)
        expect(marks).toEqual(["Fire", "fire"])
        expect(container.textContent).toBe("Fire and fireball")
    })

    it("highlights non-English text", () => {
        const { container } = render(<HighlightText text="火球术" query="火球" />)
        expect(container.querySelector("mark")?.textContent).toBe("火球")
    })

    it("renders plain text when the query is empty or whitespace", () => {
        const { container } = render(<HighlightText text="Dragon" query="  " />)
        expect(container.querySelector("mark")).toBeNull()
        expect(container.textContent).toBe("Dragon")
    })

    it("treats regex characters in the query literally", () => {
        const { container } = render(<HighlightText text="a.b (c)" query="(c)" />)
        expect(container.querySelector("mark")?.textContent).toBe("(c)")
    })
})
