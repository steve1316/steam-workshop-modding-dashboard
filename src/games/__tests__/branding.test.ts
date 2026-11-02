import { describe, expect, it } from "vitest"
import { getBranding, getGame, listGames } from "@/games/registry"
import "@/games/chrono_ark"
import "@/games/total_war_warhammer_3"

describe("game branding", () => {
    it("gives every registered game a logo, accent, gradient, and subtitle", () => {
        expect(listGames().map((g) => g.id)).toEqual(expect.arrayContaining(["chrono_ark", "total_war_warhammer_3"]))
        for (const { branding } of listGames()) {
            expect(branding.logo).toBeTruthy()
            expect(branding.accent).toMatch(/^#|^var\(/)
            expect(branding.gradient).toMatch(/linear-gradient/)
            expect(branding.subtitle.length).toBeGreaterThan(0)
        }
    })

    it("getBranding returns the manifest's branding for a registered id", () => {
        expect(getBranding("chrono_ark")).toBe(getGame("chrono_ark")?.branding)
    })

    it("getBranding returns a neutral fallback for an unknown id", () => {
        const fallback = getBranding("nonexistent_game")
        expect(fallback.logo).toBe("")
        expect(fallback.subtitle).toBe("")
        expect(fallback.accent).toBe("var(--text-dim)")
        expect(fallback.gradient).toMatch(/linear-gradient/)
    })
})
