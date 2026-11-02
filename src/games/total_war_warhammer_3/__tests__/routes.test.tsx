import { render, screen } from "@/testUtils"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TotalWarWarhammer3Routes } from "@/games/total_war_warhammer_3/routes"
import { tw3Nav } from "@/games/total_war_warhammer_3/nav"
import { _resetUseValidationForTests } from "@/games/total_war_warhammer_3/hooks/useValidation"

afterEach(() => {
    _resetUseValidationForTests()
    vi.restoreAllMocks()
})

describe("TW3 routes", () => {
    it("redirects the retired /validate path to Supported Mods", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ mods: [], issues: [] }), { status: 200 }))
        render(
            <MemoryRouter initialEntries={["/validate"]}>
                <TotalWarWarhammer3Routes />
            </MemoryRouter>
        )
        expect(await screen.findByRole("heading", { name: "Supported Mods", level: 1 })).toBeInTheDocument()
    })

    it("no longer lists Validate in the sidebar nav", () => {
        expect(tw3Nav.map((entry) => entry.label)).not.toContain("Validate")
    })
})
