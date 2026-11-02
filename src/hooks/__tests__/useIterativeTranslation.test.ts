import { renderHook, act, waitFor } from "@/testUtils"
import { useIterativeTranslation } from "@/hooks/useIterativeTranslation"
import type { BatchDescriptor } from "@/hooks/useIterativeTranslation"

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
    mockFetch.mockReset()
})

const MOD_ID = "test-mod"
const GAME_ID = "chrono_ark"

function makePlan(count: number = 1): BatchDescriptor[] {
    return Array.from({ length: count }, (_, i) => ({
        source_lang: "Korean",
        keys: [`key_${i}`],
        size: 1,
    }))
}

function successResponse(translations: Record<string, string>, suggestions: unknown[] = []) {
    return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ translations, suggestions }),
    })
}

function errorResponse(detail: string) {
    return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail }),
    })
}

describe("useIterativeTranslation", () => {
    it("starts in idle phase", () => {
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        expect(result.current.state.phase).toBe("idle")
    })

    it("startTranslation transitions to translating phase", async () => {
        mockFetch.mockReturnValue(new Promise(() => {}))
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        act(() => {
            result.current.startTranslation("claude", makePlan(1))
        })
        expect(result.current.state.phase).toBe("translating")
    })

    it("successful single batch transitions to complete", async () => {
        mockFetch.mockReturnValue(successResponse({ key_0: "Hello" }))
        const onBatch = vi.fn()
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, onBatch))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(1))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("complete"))
        expect(onBatch).toHaveBeenCalledWith({ key_0: "Hello" })
    })

    it("successful batch with suggestions transitions to reviewing", async () => {
        mockFetch.mockReturnValue(
            successResponse({ key_0: "Hello" }, [{ english: "Term", source: "텀", source_lang: "Korean", category: "custom", reason: "test" }]),
        )
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(2))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("reviewing"))
    })

    it("continueAfterReview advances to next batch", async () => {
        mockFetch
            .mockReturnValueOnce(
                successResponse({ key_0: "A" }, [{ english: "T", source: "t", source_lang: "Korean", category: "c", reason: "r" }]),
            )
            .mockReturnValueOnce(successResponse({ key_1: "B" }))
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(2))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("reviewing"))
        await act(async () => {
            result.current.continueAfterReview()
        })
        await waitFor(() => expect(result.current.state.phase).toBe("complete"))
    })

    it("last batch with suggestions transitions to reviewing then complete", async () => {
        mockFetch.mockReturnValue(
            successResponse({ key_0: "Hello" }, [{ english: "T", source: "t", source_lang: "Korean", category: "c", reason: "r" }]),
        )
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(1))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("reviewing"))
        await act(async () => {
            result.current.continueAfterReview()
        })
        expect(result.current.state.phase).toBe("complete")
    })

    it("failed fetch transitions to error phase", async () => {
        mockFetch.mockReturnValue(errorResponse("Provider unavailable"))
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(1))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("error"))
        if (result.current.state.phase === "error") {
            expect(result.current.state.message).toBe("Provider unavailable")
        }
    })

    it("cancel resets to idle", async () => {
        mockFetch.mockReturnValue(new Promise(() => {}))
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        act(() => {
            result.current.startTranslation("claude", makePlan(1))
        })
        expect(result.current.state.phase).toBe("translating")
        mockFetch.mockReturnValue(Promise.resolve({ ok: true }))
        act(() => {
            result.current.cancel()
        })
        expect(result.current.state.phase).toBe("idle")
    })

    it("cancel sends cancel request to backend", async () => {
        mockFetch.mockReturnValue(new Promise(() => {}))
        const { result } = renderHook(() => useIterativeTranslation(GAME_ID, MOD_ID, vi.fn()))
        act(() => {
            result.current.startTranslation("claude", makePlan(1))
        })
        mockFetch.mockReturnValue(Promise.resolve({ ok: true }))
        act(() => {
            result.current.cancel()
        })
        const cancelCall = mockFetch.mock.calls.find(
            (call) => typeof call[0] === "string" && call[0].includes("/translate/cancel"),
        )
        expect(cancelCall).toBeTruthy()
    })

    it("uses the provided gameId in the batch request URL", async () => {
        mockFetch.mockReturnValue(successResponse({ key_0: "Hello" }))
        const { result } = renderHook(() => useIterativeTranslation("total_war_warhammer_3", MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("claude", makePlan(1))
        })
        await waitFor(() => expect(result.current.state.phase).toBe("complete"))
        const batchCall = mockFetch.mock.calls.find(
            (call) => typeof call[0] === "string" && call[0].includes("/translate/batch"),
        )
        expect(batchCall).toBeTruthy()
        expect(String(batchCall![0])).toContain("/games/total_war_warhammer_3/translate/batch")
    })

    it("sends the run mode with a streamed batch", async () => {
        mockFetch.mockReturnValue(errorResponse("stop"))
        const { result } = renderHook(() => useIterativeTranslation("total_war_warhammer_3", MOD_ID, vi.fn()))
        await act(async () => {
            result.current.startTranslation("ollama", makePlan(1), "update")
        })
        await waitFor(() => expect(result.current.state.phase).toBe("error"))
        const streamCall = mockFetch.mock.calls.find((call) => typeof call[0] === "string" && call[0].includes("/translate/batch/stream"))
        expect(streamCall).toBeTruthy()
        expect(JSON.parse(streamCall![1].body).mode).toBe("update")
    })
})
