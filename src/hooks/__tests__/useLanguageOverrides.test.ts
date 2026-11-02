import { act, renderHook } from "@/testUtils"
import { describe, expect, it, vi } from "vitest"

import { useLanguageOverrides, type LanguageOverrides } from "@/hooks/useLanguageOverrides"

const DEFAULTS = { source: "Chinese", target: "Chinese" }

describe("useLanguageOverrides", () => {
    it("translates a non-English source into English and clears the target", async () => {
        const save = vi.fn().mockResolvedValue(undefined)
        const saved: LanguageOverrides = { source: "English", target: "Korean" }
        const { result } = renderHook(() => useLanguageOverrides(saved, DEFAULTS, save, vi.fn()))
        expect(result.current.target).toBe("Korean")
        await act(() => result.current.controls.onSourceChange("Japanese"))
        expect(save).toHaveBeenCalledWith({ source: "Japanese", target: null })
    })

    it("reports a failed save", async () => {
        const onError = vi.fn()
        const { result } = renderHook(() => useLanguageOverrides({ source: null, target: null }, DEFAULTS, () => Promise.reject(new Error("HTTP 500")), onError))
        expect(result.current.source).toBe("Chinese")
        expect(result.current.target).toBe("English")
        await act(() => result.current.controls.onTargetChange("Korean"))
        expect(onError).toHaveBeenCalledWith("Language save failed: HTTP 500")
    })
})
