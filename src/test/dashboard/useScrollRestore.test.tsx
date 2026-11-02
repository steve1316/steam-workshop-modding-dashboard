import { render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { rememberScrollTarget, useScrollRestore } from "@/dashboard/useScrollRestore"

/**
 * Renders one card with id 42 and runs the hook.
 *
 * @param ready Whether the dashboard list has loaded.
 * @returns The probe markup.
 */
function Probe({ ready }: { ready: boolean }) {
    useScrollRestore(ready)
    return <div data-mod-id="42">card</div>
}

// jsdom has no scrollIntoView.
const scrollIntoView = vi.fn()

beforeEach(() => {
    scrollIntoView.mockClear()
    Element.prototype.scrollIntoView = scrollIntoView
})

afterEach(() => {
    Reflect.deleteProperty(Element.prototype, "scrollIntoView")
    sessionStorage.clear()
})

describe("useScrollRestore", () => {
    it("keeps the target until the list is ready, then scrolls to that card once", async () => {
        rememberScrollTarget("42")
        const { rerender } = render(<Probe ready={false} />)
        expect(sessionStorage.getItem("lastViewedMod")).toBe("42")
        rerender(<Probe ready />)
        await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "instant", block: "center" }))
        expect(sessionStorage.getItem("lastViewedMod")).toBeNull()
    })

    it("drops a target whose card is gone without throwing", async () => {
        rememberScrollTarget("999")
        render(<Probe ready />)
        await waitFor(() => expect(sessionStorage.getItem("lastViewedMod")).toBeNull())
        await new Promise((resolve) => requestAnimationFrame(resolve))
        expect(scrollIntoView).not.toHaveBeenCalled()
    })

    it("does nothing when no card was remembered", async () => {
        render(<Probe ready />)
        await new Promise((resolve) => requestAnimationFrame(resolve))
        expect(scrollIntoView).not.toHaveBeenCalled()
    })
})
