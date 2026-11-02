import { act, renderHook } from "@/testUtils"
import { afterEach, describe, expect, it } from "vitest"
import { _resetUseRunnerLogForTests, appendLine, clearLog, useRunnerLog, MAX_LINES } from "@/games/total_war_warhammer_3/hooks/useRunnerLog"

afterEach(() => _resetUseRunnerLogForTests())

describe("useRunnerLog", () => {
    it("starts empty", () => {
        const { result } = renderHook(() => useRunnerLog())
        expect(result.current).toEqual([])
    })

    it("appendLine adds a data entry and notifies subscribers", () => {
        const { result } = renderHook(() => useRunnerLog())
        act(() => appendLine({ kind: "data", line: "hello", ts: "2026-05-12T00:00:00Z" }))
        expect(result.current).toHaveLength(1)
        expect(result.current[0]).toEqual({ kind: "data", line: "hello", ts: "2026-05-12T00:00:00Z" })
    })

    it("appendLine adds a separator entry", () => {
        const { result } = renderHook(() => useRunnerLog())
        act(() => appendLine({ kind: "separator", text: "--- start ---" }))
        expect(result.current).toHaveLength(1)
        expect(result.current[0]).toEqual({ kind: "separator", text: "--- start ---" })
    })

    it("caps the buffer at MAX_LINES (oldest dropped FIFO)", () => {
        const { result } = renderHook(() => useRunnerLog())
        act(() => {
            for (let i = 0; i < MAX_LINES + 5; i++) {
                appendLine({ kind: "data", line: `line-${i}`, ts: "" })
            }
        })
        expect(result.current).toHaveLength(MAX_LINES)
        expect(result.current[0]).toMatchObject({ kind: "data", line: "line-5" })
        expect(result.current[result.current.length - 1]).toMatchObject({ kind: "data", line: `line-${MAX_LINES + 4}` })
    })

    it("clearLog empties the buffer and notifies", () => {
        const { result } = renderHook(() => useRunnerLog())
        act(() => appendLine({ kind: "data", line: "x", ts: "" }))
        expect(result.current).toHaveLength(1)
        act(() => clearLog())
        expect(result.current).toEqual([])
    })

    it("state survives unmount/remount (module-level singleton)", () => {
        const first = renderHook(() => useRunnerLog())
        act(() => appendLine({ kind: "data", line: "persisted", ts: "" }))
        first.unmount()

        const second = renderHook(() => useRunnerLog())
        expect(second.result.current).toHaveLength(1)
        expect(second.result.current[0]).toMatchObject({ line: "persisted" })
    })
})
