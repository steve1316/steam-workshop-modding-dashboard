import { render, screen } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { registerGame } from "@/games/registry"
import { useActiveGame } from "@/games/useActiveGame"

registerGame({ id: "chrono_ark", slug: "chrono_ark", displayName: "Chrono Ark", icon: "chrono_ark", nav: [], routes: () => null as never })

function Probe() {
    const active = useActiveGame()
    return <div data-testid="out">{active ? `${active.slug}:${active.id}` : "none"}</div>
}

describe("useActiveGame", () => {
    it("resolves id+slug from the :gameSlug route param", () => {
        render(
            <MemoryRouter initialEntries={["/chrono_ark/dashboard"]}>
                <Routes>
                    <Route path="/:gameSlug/*" element={<Probe />} />
                </Routes>
            </MemoryRouter>
        )
        expect(screen.getByTestId("out").textContent).toBe("chrono_ark:chrono_ark")
    })
})
