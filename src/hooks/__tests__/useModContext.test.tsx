import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@/testUtils"
import { describe, expect, it, vi } from "vitest"

import { createQueryClient } from "@/lib/queryClient"
import { useModContext } from "@/hooks/useModContext"

const EMPTY = { source_game: "", character_name: "", background: "" }

/**
 * Render `useModContext` against a fresh query cache.
 *
 * @param save The store's save call.
 * @returns The rendered hook.
 */
function setup(save: (next: typeof EMPTY) => Promise<void>) {
    const client = createQueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
    const load = async () => ({ ...EMPTY, character_name: "Lucy" })
    return renderHook(() => useModContext(["test", "context"], { load, save }, EMPTY), { wrapper })
}

describe("useModContext", () => {
    it("loads the context and merges a save into it", async () => {
        const save = vi.fn().mockResolvedValue(undefined)
        const { result } = setup(save)
        await waitFor(() => expect(result.current.loading).toBe(false))
        expect(result.current.hasContext).toBe(true)
        await act(() => result.current.save({ background: "A healer." }))
        expect(save).toHaveBeenCalledWith({ source_game: "", character_name: "Lucy", background: "A healer." })
        await waitFor(() => expect(result.current.context.background).toBe("A healer."))
    })

    it("rolls back a save the backend refuses", async () => {
        const { result } = setup(() => Promise.reject(new Error("HTTP 500")))
        await waitFor(() => expect(result.current.loading).toBe(false))
        await act(() => expect(result.current.save({ character_name: "Bob" })).rejects.toThrow("HTTP 500"))
        await waitFor(() => expect(result.current.context.character_name).toBe("Lucy"))
    })
})
