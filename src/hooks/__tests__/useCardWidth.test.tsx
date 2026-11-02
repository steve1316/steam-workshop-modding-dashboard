import { act, render, screen } from "@/testUtils"
import { useRef } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCardWidth } from "@/hooks/useCardWidth"

/**
 * Renders a wrapper holding `count` cards and prints the width the hook reports.
 *
 * @param count Number of `.mod-card` elements to render.
 * @returns The probe markup.
 */
function Probe({ count }: { count: number }) {
    const ref = useRef<HTMLDivElement>(null)
    const width = useCardWidth(ref, count)
    return (
        <div ref={ref}>
            {Array.from({ length: count }, (_, i) => (
                <div key={i} className="mod-card" />
            ))}
            <output>{width ?? "none"}</output>
        </div>
    )
}

let cardWidth = 333

beforeEach(() => {
    cardWidth = 333
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({ width: cardWidth }) as DOMRect)
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

describe("useCardWidth", () => {
    it("measures the first card once when ResizeObserver is missing", () => {
        vi.stubGlobal("ResizeObserver", undefined)
        render(<Probe count={2} />)
        expect(screen.getByRole("status")).toHaveTextContent("333")
    })

    it("re-measures when the wrapper resizes", () => {
        let onResize = () => {}
        vi.stubGlobal(
            "ResizeObserver",
            class {
                constructor(callback: () => void) {
                    onResize = callback
                }
                observe() {}
                disconnect() {}
            }
        )
        render(<Probe count={1} />)
        cardWidth = 400
        act(() => onResize())
        expect(screen.getByRole("status")).toHaveTextContent("400")
    })

    it("keeps the last width when the search hides every card", () => {
        vi.stubGlobal("ResizeObserver", undefined)
        const { rerender } = render(<Probe count={1} />)
        rerender(<Probe count={0} />)
        expect(screen.getByRole("status")).toHaveTextContent("333")
    })

    it("ignores a zero width from a hidden grid", () => {
        vi.stubGlobal("ResizeObserver", undefined)
        cardWidth = 0
        render(<Probe count={1} />)
        expect(screen.getByRole("status")).toHaveTextContent("none")
    })
})
