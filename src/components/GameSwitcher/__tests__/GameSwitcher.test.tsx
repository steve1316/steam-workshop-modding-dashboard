import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import GameSwitcher from "@/components/GameSwitcher"
import "@/games/chrono_ark" // side-effect: registers manifest (so slugForId resolves)
import "@/games/total_war_warhammer_3" // side-effect: registers manifest

const GAMES = [
    { game_id: "chrono_ark", display_name: "Chrono Ark", icon: "", capabilities: [] },
    { game_id: "total_war_warhammer_3", display_name: "Warhammer III", icon: "", capabilities: [] },
]

const navigateMock = vi.fn()

vi.mock("react-router-dom", async () => {
    const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
    return { ...actual, useNavigate: () => navigateMock }
})

const wrap = (ui: React.ReactNode) => <MemoryRouter>{ui}</MemoryRouter>

beforeEach(() => {
    navigateMock.mockReset()
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        const url = String(input)
        if (url.endsWith("/games")) {
            return Promise.resolve(new Response(JSON.stringify(GAMES), { status: 200 }))
        }
        if (url.endsWith("/settings")) {
            return Promise.resolve(new Response("", { status: 200 }))
        }
        return Promise.reject(new Error(`unexpected fetch: ${url}`))
    })
})

afterEach(() => vi.restoreAllMocks())

describe("GameSwitcher (segmented)", () => {
    it("renders nothing while the games list is empty", () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
        const { container } = render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        expect(container).toBeEmptyDOMElement()
    })

    it("renders one radio pill per game with the active pill marked aria-checked", async () => {
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const group = await screen.findByRole("radiogroup", { name: /active game/i })
        const pills = await screen.findAllByRole("radio")
        expect(group).toBeInTheDocument()
        expect(pills).toHaveLength(2)
        expect(screen.getByRole("radio", { name: /Chrono Ark/i })).toHaveAttribute("aria-checked", "true")
        expect(screen.getByRole("radio", { name: /Warhammer III/i })).toHaveAttribute("aria-checked", "false")
    })

    it("renders each pill's logo image with the display name as alt text", async () => {
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        await screen.findByRole("radiogroup", { name: /active game/i })
        expect(screen.getByAltText("Chrono Ark")).toBeInTheDocument()
        expect(screen.getByAltText("Warhammer III")).toBeInTheDocument()
    })

    it("clicking an inactive pill POSTs the settings and navigates to the new game's slug dashboard", async () => {
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const user = userEvent.setup()
        const inactive = await screen.findByRole("radio", { name: /Warhammer III/i })
        await user.click(inactive)
        const calls = vi.mocked(globalThis.fetch).mock.calls
        const settingsCall = calls.find(([url]) => String(url).endsWith("/settings"))
        expect(settingsCall).toBeTruthy()
        expect(JSON.parse(String(settingsCall![1]!.body))).toEqual({ active_game: "total_war_warhammer_3" })
        expect(navigateMock).toHaveBeenCalledWith("/warhammer_3/dashboard")
    })

    it("navigates immediately without waiting for the settings POST to finish", async () => {
        vi.mocked(globalThis.fetch).mockImplementation((input) => {
            const url = String(input)
            if (url.endsWith("/games")) return Promise.resolve(new Response(JSON.stringify(GAMES), { status: 200 }))
            // The settings POST never settles, so navigation must not depend on it.
            return new Promise<Response>(() => {})
        })
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const user = userEvent.setup()
        await user.click(await screen.findByRole("radio", { name: /Warhammer III/i }))
        expect(navigateMock).toHaveBeenCalledWith("/warhammer_3/dashboard")
    })

    it("clicking the already-active pill does nothing", async () => {
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const user = userEvent.setup()
        const active = await screen.findByRole("radio", { name: /Chrono Ark/i })
        await user.click(active)
        const calls = vi.mocked(globalThis.fetch).mock.calls
        const settingsCall = calls.find(([url]) => String(url).endsWith("/settings"))
        expect(settingsCall).toBeUndefined()
        expect(navigateMock).not.toHaveBeenCalled()
    })

    it("ArrowRight from the active pill moves focus to the other pill, and Enter selects it", async () => {
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const user = userEvent.setup()
        const active = await screen.findByRole("radio", { name: /Chrono Ark/i })
        active.focus()
        await user.keyboard("{ArrowRight}")
        expect(screen.getByRole("radio", { name: /Warhammer III/i })).toHaveFocus()
        await user.keyboard("{Enter}")
        expect(navigateMock).toHaveBeenCalledWith("/warhammer_3/dashboard")
    })

    it("renders a single-letter fallback glyph for a game with no branding entry", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementationOnce(() =>
            Promise.resolve(new Response(JSON.stringify([...GAMES, { game_id: "future_game", display_name: "Future Game", icon: "", capabilities: [] }]), { status: 200 }))
        )
        render(wrap(<GameSwitcher activeGameId="chrono_ark" />))
        const futurePill = await screen.findByRole("radio", { name: /Future Game/i })
        expect(futurePill).toBeInTheDocument()
        expect(futurePill).toHaveTextContent("F")
        expect(screen.queryByAltText("Future Game")).toBeNull()
    })
})
