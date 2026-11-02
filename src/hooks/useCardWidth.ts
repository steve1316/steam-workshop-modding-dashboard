import { useEffect, useState, type RefObject } from "react"

/**
 * Tracks the rendered width of the first `.mod-card` inside a wrapper, so a dashboard search field can match the grid's column width.
 *
 * @param wrapperRef Element that contains the card grid.
 * @param itemCount Number of cards rendered. A change re-measures, since the first card may have just appeared.
 * @returns The first card's width in pixels, or undefined until a visible card has rendered.
 */
export function useCardWidth(wrapperRef: RefObject<HTMLElement | null>, itemCount: number): number | undefined {
    const [width, setWidth] = useState<number | undefined>(undefined)

    useEffect(() => {
        const wrapper = wrapperRef.current
        if (!wrapper) return

        const update = () => {
            const firstCard = wrapper.querySelector(".mod-card")
            const next = firstCard?.getBoundingClientRect().width ?? 0
            // A hidden or empty grid reports 0. Keep the last real width instead of collapsing the search field.
            if (next > 0) setWidth(next)
        }

        update()
        // jsdom has no ResizeObserver. One measurement is enough there.
        if (typeof ResizeObserver === "undefined") return
        const observer = new ResizeObserver(update)
        observer.observe(wrapper)
        return () => observer.disconnect()
    }, [wrapperRef, itemCount])

    return width
}
