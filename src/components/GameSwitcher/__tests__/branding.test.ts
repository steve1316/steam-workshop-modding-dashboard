import { describe, expect, it } from "vitest"
import { GAME_BRANDING, getBranding } from "@/components/GameSwitcher/branding"

describe("GameSwitcher branding map", () => {
    it("defines branding entries for chrono_ark and total_war_warhammer_3", () => {
        expect(GAME_BRANDING.chrono_ark).toBeDefined()
        expect(GAME_BRANDING.total_war_warhammer_3).toBeDefined()
    })

    it("each registered branding entry has logo, accent, gradient, and subtitle", () => {
        for (const id of ["chrono_ark", "total_war_warhammer_3"] as const) {
            const b = GAME_BRANDING[id]
            expect(b.logo).toBeTruthy()
            expect(b.accent).toMatch(/^#|^var\(/)
            expect(b.gradient).toMatch(/linear-gradient/)
            expect(b.subtitle.length).toBeGreaterThan(0)
        }
    })

    it("getBranding returns the registered entry for a known id", () => {
        expect(getBranding("chrono_ark")).toBe(GAME_BRANDING.chrono_ark)
    })

    it("getBranding returns a neutral fallback for an unknown id", () => {
        const fallback = getBranding("nonexistent_game")
        expect(fallback.logo).toBe("")
        expect(fallback.subtitle).toBe("")
        expect(fallback.accent).toBe("var(--text-dim)")
        expect(fallback.gradient).toMatch(/linear-gradient/)
    })
})
