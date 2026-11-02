import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useRescanAll } from "@/games/total_war_warhammer_3/hooks/useRescanAll"
import { rescanMod } from "@/games/total_war_warhammer_3/lib/translationApi"
import type { WH3RescanSummary } from "@/games/total_war_warhammer_3/lib/types"

vi.mock("@/games/total_war_warhammer_3/lib/translationApi", () => ({ rescanMod: vi.fn() }))

const rescan = vi.mocked(rescanMod)

/**
 * Builds a rescan result for one mod.
 *
 * @param id Workshop id.
 * @returns A minimal summary.
 */
const summary = (id: string) => ({ mod_id: id, counts: { translated: 1, untranslated: 0, stale: 0, orphan: 0 } }) as unknown as WH3RescanSummary

/**
 * Makes `rescanMod` return one held promise per call, released in call order.
 *
 * @returns The release functions, one per started rescan.
 */
function holdRescans() {
    const release: Array<() => void> = []
    rescan.mockImplementation((id: string) => new Promise<WH3RescanSummary>((resolve) => release.push(() => resolve(summary(id)))))
    return release
}

afterEach(() => {
    rescan.mockReset()
})

describe("useRescanAll", () => {
    it("rescans one mod at a time and reports its position while running", async () => {
        const release = holdRescans()
        const { result } = renderHook(() => useRescanAll())
        let done: Promise<number> = Promise.resolve(0)
        act(() => {
            done = result.current.rescanAll(["a", "b"])
        })
        expect(result.current.running).toBe(true)
        expect(result.current.progress).toEqual({ current: 1, total: 2 })
        expect(rescan).toHaveBeenCalledTimes(1)

        await act(async () => release[0]())
        expect(result.current.progressByMod.a).toEqual(summary("a"))
        expect(result.current.progress).toEqual({ current: 2, total: 2 })
        expect(rescan).toHaveBeenLastCalledWith("b", expect.any(AbortSignal))

        await act(async () => {
            release[1]()
            await done
        })
        expect(result.current.progressByMod.b).toEqual(summary("b"))
        expect(result.current.running).toBe(false)
        expect(result.current.progress).toBeNull()
    })

    it("keeps going when one rescan fails and leaves that mod without a result", async () => {
        rescan.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(summary("b"))
        const { result } = renderHook(() => useRescanAll())
        await act(() => result.current.rescanAll(["a", "b"]))
        expect(result.current.progressByMod.a ?? null).toBeNull()
        expect(result.current.progressByMod.b).toEqual(summary("b"))
        expect(result.current.running).toBe(false)
    })

    it("stops after unmount and never starts the next rescan", async () => {
        const release = holdRescans()
        const { result, unmount } = renderHook(() => useRescanAll())
        act(() => {
            void result.current.rescanAll(["a", "b"])
        })
        unmount()
        expect((rescan.mock.calls[0][1] as AbortSignal).aborted).toBe(true)
        release[0]()
        await new Promise((resolve) => setTimeout(resolve, 10))
        expect(rescan).toHaveBeenCalledTimes(1)
    })

    it("cancels a running batch when a new one starts", async () => {
        const release = holdRescans()
        const { result } = renderHook(() => useRescanAll())
        act(() => {
            void result.current.rescanAll(["a", "b"])
        })
        act(() => {
            void result.current.rescanAll(["c"])
        })
        expect((rescan.mock.calls[0][1] as AbortSignal).aborted).toBe(true)
        await act(async () => release[0]())
        await act(async () => release[1]())
        expect(result.current.progressByMod.a ?? null).toBeNull()
        expect(result.current.progressByMod.c).toEqual(summary("c"))
        expect(rescan.mock.calls.map((call) => call[0])).toEqual(["a", "c"])
        expect(result.current.running).toBe(false)
    })

    it("rescans a single mod and ignores its failure", async () => {
        rescan.mockResolvedValueOnce(summary("a")).mockRejectedValueOnce(new Error("boom"))
        const { result } = renderHook(() => useRescanAll())
        await act(() => result.current.rescanOne("a"))
        expect(result.current.progressByMod.a).toEqual(summary("a"))
        await act(() => result.current.rescanOne("a"))
        expect(result.current.progressByMod.a).toEqual(summary("a"))
    })

    it("reports how many rescans failed and keeps the failed mod's earlier result", async () => {
        rescan.mockResolvedValueOnce(summary("a")).mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(summary("b"))
        const { result } = renderHook(() => useRescanAll())
        await act(() => result.current.rescanOne("a"))
        let failed = -1
        await act(async () => {
            failed = await result.current.rescanAll(["a", "b"])
        })
        expect(failed).toBe(1)
        expect(result.current.progressByMod.a).toEqual(summary("a"))
        expect(result.current.progressByMod.b).toEqual(summary("b"))
        expect(rescan.mock.calls.map((call) => call[0])).toEqual(["a", "a", "b"])
    })
})
