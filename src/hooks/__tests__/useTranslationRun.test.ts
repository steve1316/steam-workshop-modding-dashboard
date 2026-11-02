import { act, renderHook, waitFor } from "@/testUtils"
import { QueryClientProvider } from "@tanstack/react-query"
import { createElement, type ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { BatchState } from "@/hooks/useIterativeTranslation"
import { useTranslationRun, type RunPreview } from "@/hooks/useTranslationRun"
import { createQueryClient } from "@/lib/queryClient"

const loop = vi.hoisted(() => ({ state: { phase: "idle" } as BatchState, startTranslation: vi.fn(), continueAfterReview: vi.fn(), cancel: vi.fn() }))
vi.mock("@/hooks/useIterativeTranslation", () => ({ useIterativeTranslation: () => loop }))

const refresh = vi.fn().mockResolvedValue(undefined)
vi.mock("@/hooks/usePendingSuggestions", () => ({ usePendingSuggestions: () => ({ suggestions: [], refresh, scan: vi.fn(), scanning: false }) }))

/**
 * Render the hook with `/settings` answering `provider`.
 *
 * @param options Extra hook options.
 * @returns The rendered hook.
 */
function setup(options: { autoOpenReview?: boolean; onSettled?: (state: BatchState) => void } = {}) {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ provider: "claude" })))
    const client = createQueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client }, children)
    return renderHook(() => useTranslationRun<RunPreview>({ gameId: "chrono_ark", modId: "1", onBatchTranslated: vi.fn(), ...options }), { wrapper })
}

beforeEach(() => {
    loop.state = { phase: "idle" }
})

afterEach(() => {
    vi.restoreAllMocks()
})

describe("useTranslationRun", () => {
    it("previews with the saved provider and starts the confirmed plan", async () => {
        const { result } = setup()
        await waitFor(() => expect(result.current.provider).toBe("claude"))
        const plan = [{ source_lang: "Chinese", keys: ["a"], size: 1 }]
        const load = vi.fn().mockResolvedValue({ total_strings: 1, batch_plan: plan })
        await act(() => result.current.openPreview("", load))
        expect(load).toHaveBeenCalledWith("claude")
        act(() => result.current.confirmPreview())
        expect(loop.startTranslation).toHaveBeenCalledWith("claude", plan, undefined)
        expect(result.current.preview).toBeNull()
    })

    it("reports an empty or failed preview in the banner", async () => {
        const { result } = setup()
        await act(() => result.current.openPreview("openai", async () => ({ total_strings: 0 })))
        expect(result.current.banner).toEqual({ type: "success", message: "All strings are already translated." })
        await act(() => result.current.openPreview("openai", () => Promise.reject(new Error("HTTP 500")), { failure: "Names preview failed" }))
        expect(result.current.banner).toEqual({ type: "error", message: "Names preview failed: HTTP 500" })
    })

    it("shows a failed run's error until it is dismissed", () => {
        const onSettled = vi.fn()
        const { result, rerender } = setup({ onSettled })
        loop.state = { phase: "error", message: "Provider timed out.", completedBatches: 2 }
        rerender()
        expect(result.current.banner).toEqual({ type: "error", message: "Provider timed out. 2 batch(es) completed before the error." })
        expect(onSettled).toHaveBeenCalledTimes(1)
        expect(refresh).toHaveBeenCalled()
        act(() => result.current.setBanner(null))
        expect(result.current.banner).toBeNull()
    })

    it("opens the review on a pause only when asked to, and remembers a close", () => {
        const paused: BatchState = { phase: "reviewing", batchIndex: 0, totalBatches: 2, suggestions: [] }
        const manual = setup()
        loop.state = paused
        manual.rerender()
        expect(manual.result.current.review).toBeNull()
        act(() => manual.result.current.pausedBanner!.onReview())
        expect(manual.result.current.review).not.toBeNull()

        const auto = setup({ autoOpenReview: true })
        expect(auto.result.current.review).not.toBeNull()
        act(() => auto.result.current.review!.onClose())
        expect(auto.result.current.review).toBeNull()
        expect(auto.result.current.pausedBanner).not.toBeNull()
    })
})
