import { render, screen, withActiveGame } from "@/testUtils"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import Sidebar from "@/components/Sidebar"
import "@/games/chrono_ark"
import "@/games/total_war_warhammer_3"

const GAMES = [
    { game_id: "chrono_ark", display_name: "Chrono Ark", icon: "", capabilities: [] },
    { game_id: "total_war_warhammer_3", display_name: "Warhammer III", icon: "", capabilities: [] },
]

const wrap = (gameId: string) => <MemoryRouter>{withActiveGame(gameId, <Sidebar />)}</MemoryRouter>

beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        const url = String(input)
        if (url.endsWith("/games")) {
            return Promise.resolve(new Response(JSON.stringify(GAMES), { status: 200 }))
        }
        return Promise.reject(new Error(`unexpected fetch: ${url}`))
    })
})

afterEach(() => vi.restoreAllMocks())

describe("Sidebar active-game header", () => {
    it("renders the active game's display name as the header title", async () => {
        render(wrap("chrono_ark"))
        const title = await screen.findByTestId("sidebar-game-title")
        expect(title).toHaveTextContent("Chrono Ark")
    })

    it("renders the active game's branding subtitle", async () => {
        render(wrap("chrono_ark"))
        const subtitle = await screen.findByTestId("sidebar-game-subtitle")
        expect(subtitle).toHaveTextContent("Translation tools")
    })

    it("switches the title and subtitle when the active game changes", async () => {
        const { rerender } = render(wrap("chrono_ark"))
        const titleBefore = await screen.findByTestId("sidebar-game-title")
        expect(titleBefore).toHaveTextContent("Chrono Ark")
        rerender(wrap("total_war_warhammer_3"))
        const titleAfter = await screen.findByTestId("sidebar-game-title")
        expect(titleAfter).toHaveTextContent("Warhammer III")
        expect(screen.getByTestId("sidebar-game-subtitle")).toHaveTextContent("Workshop tools")
    })

    it("renders a divider element between the game header and nav links", async () => {
        render(wrap("chrono_ark"))
        const divider = await screen.findByTestId("sidebar-game-divider")
        expect(divider).toBeInTheDocument()
    })
})
