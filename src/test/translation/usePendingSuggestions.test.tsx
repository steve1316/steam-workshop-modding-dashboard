import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { usePendingSuggestions } from "@/hooks/usePendingSuggestions"

const SUGGESTION = { english: "Roland", source: "罗兰", source_lang: "Chinese", category: "characters", reason: "Recurring name" }

/**
 * Build a JSON response.
 *
 * @param body Response body.
 * @param status HTTP status.
 * @returns The response.
 */
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }))

afterEach(() => vi.restoreAllMocks())

describe("usePendingSuggestions", () => {
    it("loads the pending suggestions on mount", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => json([SUGGESTION]))
        const { result } = renderHook(() => usePendingSuggestions("chrono_ark", "1", vi.fn()))
        await waitFor(() => expect(result.current.suggestions).toHaveLength(1))
    })

    it("scans, refreshes the list and reports how many terms were found", async () => {
        const lists = [[], [SUGGESTION]]
        vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
            if (String(input).endsWith("/scan") && init?.method === "POST") return json({ status: "success", new: 1 })
            return json(lists.length > 1 ? lists.shift() : lists[0])
        })
        const onBanner = vi.fn()
        const { result } = renderHook(() => usePendingSuggestions("total_war_warhammer_3", "1", onBanner))
        await waitFor(() => expect(result.current.suggestions).toEqual([]))
        await act(() => result.current.scan())
        expect(result.current.suggestions).toHaveLength(1)
        expect(onBanner).toHaveBeenCalledWith({ type: "success", message: "Found 1 new glossary term suggestion(s)." })
        expect(result.current.scanning).toBe(false)
    })

    it("reports a failed scan as an error and re-enables scanning", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
            if (String(input).endsWith("/scan") && init?.method === "POST") return json({ detail: "Claude is unavailable" }, 500)
            return json([])
        })
        const onBanner = vi.fn()
        const { result } = renderHook(() => usePendingSuggestions("total_war_warhammer_3", "1", onBanner))
        await act(() => result.current.scan())
        expect(onBanner).toHaveBeenCalledWith({ type: "error", message: "Scan failed: Claude is unavailable" })
        expect(result.current.scanning).toBe(false)
    })

    it("reports a network failure as an error", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
            if (init?.method === "POST") return Promise.reject(new TypeError("Failed to fetch"))
            return json([])
        })
        const onBanner = vi.fn()
        const { result } = renderHook(() => usePendingSuggestions("chrono_ark", "1", onBanner))
        await act(() => result.current.scan())
        expect(onBanner).toHaveBeenCalledWith({ type: "error", message: "Scan failed: Failed to fetch" })
    })
})
