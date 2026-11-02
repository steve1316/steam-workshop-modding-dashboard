import { QueryClientProvider } from "@tanstack/react-query"
import { render as rtlRender, type RenderOptions } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"
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
