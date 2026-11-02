import { render, screen } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { useGameSlug } from "@/games/useGameSlug"

function Probe() {
    return <div data-testid="slug">{useGameSlug() || "none"}</div>
}

/** Mirror the real app nesting: App's /:gameSlug/* renders an element that itself renders a descendant <Routes>. */
function GameSubtree() {
    return (
        <Routes>
            <Route path="dashboard" element={<Probe />} />
        </Routes>
    )
}

describe("useGameSlug", () => {
    it("reads the gameSlug param through a nested descendant <Routes>", () => {
        render(
            <MemoryRouter initialEntries={["/warhammer_3/dashboard"]}>
                <Routes>
                    <Route path="/:gameSlug/*" element={<GameSubtree />} />
                </Routes>
            </MemoryRouter>
        )
        expect(screen.getByTestId("slug").textContent).toBe("warhammer_3")
    })
})
