import { render } from "@testing-library/react"
import { highlightMatch } from "@/lib/text"

describe("highlightMatch", () => {
    it("returns plain text when query is empty", () => {
        expect(highlightMatch("Hello World", "")).toBe("Hello World")
    })

    it("returns plain text when no match found", () => {
        expect(highlightMatch("Hello World", "xyz")).toBe("Hello World")
    })

    it("wraps matching substring in a highlight span", () => {
        const result = highlightMatch("Hello World", "World")
        const { container } = render(<>{result}</>)
        const span = container.querySelector("span")
        expect(span).toHaveTextContent("World")
        expect(span).toHaveStyle({ background: "rgba(56, 189, 248, 0.3)" })
    })

    it("matches case-insensitively", () => {
        const result = highlightMatch("Hello World", "hello")
        const { container } = render(<>{result}</>)
        const span = container.querySelector("span")
        expect(span).toHaveTextContent("Hello")
    })

    it("only highlights first occurrence", () => {
        const result = highlightMatch("abcabc", "abc")
        const { container } = render(<>{result}</>)
        const spans = container.querySelectorAll("span")
        expect(spans).toHaveLength(1)
        expect(spans[0]).toHaveTextContent("abc")
        expect(container.textContent).toBe("abcabc")
    })
})
