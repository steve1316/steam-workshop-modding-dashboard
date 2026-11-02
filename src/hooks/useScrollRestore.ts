import { useEffect } from "react"

const STORAGE_KEY = "lastViewedMod"

/**
 * Remembers the card the user opened, so the dashboard can scroll back to it when they return.
 *
 * @param id The mod or workshop id on the card's `data-mod-id` attribute.
 */
export function rememberScrollTarget(id: string): void {
    sessionStorage.setItem(STORAGE_KEY, id)
}

/**
 * Scrolls to the remembered card once the dashboard list has loaded, then forgets it so later renders don't jump.
 *
 * @param ready True once the real card list has rendered. The target is kept until then so there is a card to scroll to.
 */
export function useScrollRestore(ready: boolean): void {
    useEffect(() => {
        if (!ready) return
        const id = sessionStorage.getItem(STORAGE_KEY)
        if (!id) return
        sessionStorage.removeItem(STORAGE_KEY)
        requestAnimationFrame(() => {
            document.querySelector(`[data-mod-id="${id}"]`)?.scrollIntoView({ behavior: "instant", block: "center" })
        })
    }, [ready])
}
