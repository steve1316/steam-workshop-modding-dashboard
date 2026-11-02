import { QueryClientProvider } from "@tanstack/react-query"
import { render as rtlRender, type RenderOptions } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"
import { ActiveGameContext } from "@/context/ActiveGameContext"
import { getGame } from "@/games/registry"
import { createQueryClient } from "@/lib/queryClient"

export * from "@testing-library/react"

/**
 * Testing Library's `render`, inside a fresh query client so cached data never leaks between tests.
 *
 * @param ui Element to render.
 * @param options Testing Library options. A `wrapper` here sits inside the query provider.
 * @returns The render result.
 */
export function render(ui: ReactElement, options?: RenderOptions) {
    const client = createQueryClient()
    const Inner = options?.wrapper
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{Inner ? <Inner>{children}</Inner> : children}</QueryClientProvider>
    return rtlRender(ui, { ...options, wrapper })
}

/**
 * Wrap an element in the active-game context, as the app shell does.
 *
 * @param gameId Registered game id. The test must import that game's module.
 * @param ui Element to wrap.
 * @returns The wrapped element.
 */
export function withActiveGame(gameId: string, ui: ReactNode) {
    const game = getGame(gameId)
    if (!game) throw new Error(`${gameId} is not registered. Import its game module in the test.`)
    return <ActiveGameContext value={game}>{ui}</ActiveGameContext>
}
