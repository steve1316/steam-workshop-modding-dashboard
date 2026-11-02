import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import App from "@/App"

function jsonResponse(body: unknown) {
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } })
}

afterEach(() => vi.restoreAllMocks())

describe("App game-prefixed routing", () => {
    it("derives the active game from the URL slug, not the persisted setting", async () => {
        // Persisted game is chrono_ark, but the URL is the warhammer_3 slug. The sidebar must follow the URL.
        // Every non-settings endpoint returns [] so each game's dashboard renders an empty grid instead of crashing.
        vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
            const url = String(input)
            if (url.endsWith("/settings")) return Promise.resolve(jsonResponse({ active_game: "chrono_ark" }))
            return Promise.resolve(jsonResponse([]))
        })
        render(
            <MemoryRouter initialEntries={["/warhammer_3/dashboard"]}>
                <App />
            </MemoryRouter>
        )
        // The WH3 sidebar header proves the slug (not the persisted chrono_ark) drove the active game.
        await waitFor(() => expect(screen.getByTestId("sidebar-game-title")).toHaveTextContent("Warhammer III"))
    })
})

describe("App game accent", () => {
    beforeEach(() => {
        // jsdom has no ResizeObserver. The Chrono Ark dashboard uses it to size the search bar.
        vi.stubGlobal(
            "ResizeObserver",
            class {
                observe() {}
                disconnect() {}
            }
        )
    })

    afterEach(() => {
        // Unmount before unstubbing so no pending effect reaches the missing global.
        cleanup()
        vi.unstubAllGlobals()
        document.documentElement.style.removeProperty("--game-accent")
        document.documentElement.style.removeProperty("--game-accent-gradient")
    })

    /**
     * Render the app at a URL with every endpoint returning an empty payload.
     *
     * @param path Initial URL to render.
     * @param activeGame The saved `active_game` setting.
     */
    function renderAt(path: string, activeGame = "chrono_ark") {
        vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
            const url = String(input)
            if (url.endsWith("/settings")) return Promise.resolve(jsonResponse({ active_game: activeGame }))
            return Promise.resolve(jsonResponse([]))
        })
        render(
            <MemoryRouter initialEntries={[path]}>
                <App />
            </MemoryRouter>
        )
    }

    it("sets the WH3 accent on the root element so portaled dialogs inherit it", async () => {
        renderAt("/warhammer_3/dashboard")
        const root = document.documentElement.style
        await waitFor(() => expect(root.getPropertyValue("--game-accent-gradient")).toContain("#dc2626"))
        expect(root.getPropertyValue("--game-accent")).toBe("#dc2626")
    })

    it("sets the Chrono Ark accent on the root element for chrono_ark routes", async () => {
        renderAt("/chrono_ark/dashboard")
        await waitFor(() => expect(document.documentElement.style.getPropertyValue("--game-accent-gradient")).toContain("#38bdf8"))
    })

    it("keeps the WH3 sidebar and accent when Settings is opened from a WH3 page", async () => {
        renderAt("/warhammer_3/dashboard")
        await waitFor(() => expect(screen.getByTestId("sidebar-game-title")).toHaveTextContent("Warhammer III"))
        await userEvent.click(screen.getByRole("link", { name: /Settings/ }))
        await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument())
        expect(screen.getByTestId("sidebar-game-title")).toHaveTextContent("Warhammer III")
        expect(document.documentElement.style.getPropertyValue("--game-accent")).toBe("#dc2626")
    })

    it("uses the saved game's sidebar and accent when /settings is opened directly", async () => {
        document.documentElement.style.setProperty("--game-accent-gradient", "linear-gradient(#38bdf8, #818cf8)")
        renderAt("/settings", "total_war_warhammer_3")
        await waitFor(() => expect(screen.getByTestId("sidebar-game-title")).toHaveTextContent("Warhammer III"))
        await waitFor(() => expect(document.documentElement.style.getPropertyValue("--game-accent")).toBe("#dc2626"))
    })

    it("does not carry a previous game's accent into a Chrono Ark Settings visit", async () => {
        document.documentElement.style.setProperty("--game-accent-gradient", "linear-gradient(#dc2626, #f97316)")
        renderAt("/settings")
        await waitFor(() => expect(document.documentElement.style.getPropertyValue("--game-accent-gradient")).toContain("#38bdf8"))
    })

    it("titles the browser tab after the game in the URL, and keeps it on Settings", async () => {
        renderAt("/warhammer_3/dashboard")
        await waitFor(() => expect(document.title).toBe("Warhammer III Translator"))
        await userEvent.click(screen.getByRole("link", { name: /Settings/ }))
        await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument())
        expect(document.title).toBe("Warhammer III Translator")
    })

    it("titles the browser tab Chrono Ark Translator on Chrono Ark pages", async () => {
        document.title = "Warhammer III Translator"
        renderAt("/chrono_ark/dashboard")
        await waitFor(() => expect(document.title).toBe("Chrono Ark Translator"))
    })
})
