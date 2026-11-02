import { describe, expect, it } from "vitest"
import { registerGame, getGameBySlug, idForSlug, slugForId } from "@/games/registry"

function fakeManifest(id: string, slug: string) {
    return { id, slug, displayName: id, icon: id, nav: [], routes: () => null as never }
}

describe("game registry slugs", () => {
    it("resolves a manifest by slug", () => {
        registerGame(fakeManifest("game_a", "a"))
        expect(getGameBySlug("a")?.id).toBe("game_a")
        expect(getGameBySlug("missing")).toBeUndefined()
    })

    it("maps slug<->id both ways", () => {
        registerGame(fakeManifest("game_b", "bee"))
        expect(idForSlug("bee")).toBe("game_b")
        expect(slugForId("game_b")).toBe("bee")
        expect(idForSlug("nope")).toBeUndefined()
        expect(slugForId("nope")).toBeUndefined()
    })
})
