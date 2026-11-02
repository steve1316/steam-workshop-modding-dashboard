import { cleanup, render, screen, waitFor } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import DashboardPage from "@/games/chrono_ark/pages/Dashboard"

const MOD = {
    id: "3315737452",
    name: "Zerooz Cathy",
    author: "Someone",
    total: 10,
    translated: 5,
    untranslated: 5,
    user_translated: 5,
    untouched: 0,
    percentage: 50,
    has_dll: false,
    has_changes: false,
    preview_image: null,
    url: "https://steamcommunity.com/sharedfiles/filedetails/?id=3315737452",
}

const wrap = (ui: React.ReactNode) => <MemoryRouter>{ui}</MemoryRouter>

// jsdom has no scrollIntoView. Scroll-restore calls it on the last viewed card from a requestAnimationFrame callback.
const scrollIntoView = vi.fn()

beforeEach(() => {
    // jsdom has no ResizeObserver. The dashboard only uses it to size the search bar.
    vi.stubGlobal(
        "ResizeObserver",
        class {
            observe() {}
            disconnect() {}
        }
    )
    scrollIntoView.mockClear()
    Element.prototype.scrollIntoView = scrollIntoView
})

afterEach(() => {
    // Unmount before unstubbing. Hooks run in reverse order, so RTL's own cleanup would otherwise run after the stub is gone.
    cleanup()
    vi.unstubAllGlobals()
    Reflect.deleteProperty(Element.prototype, "scrollIntoView")
    vi.restoreAllMocks()
    sessionStorage.clear()
})

describe("Chrono Ark Dashboard page", () => {
    it("shows skeleton cards while the mod list is loading", () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => {}))
        render(wrap(<DashboardPage />))
        expect(screen.getByRole("status", { name: /loading mods/i })).toBeInTheDocument()
    })

    it("replaces the skeleton with mod cards once the list arrives", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([MOD]), { status: 200 }))
        render(wrap(<DashboardPage />))
        expect(await screen.findByText("Zerooz Cathy")).toBeInTheDocument()
        expect(screen.queryByRole("status", { name: /loading mods/i })).not.toBeInTheDocument()
    })

    it("keeps the last viewed mod id until the real list has loaded so scroll-restore can find the card", async () => {
        sessionStorage.setItem("lastViewedMod", MOD.id)
        let resolve: (r: Response) => void = () => {}
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>((r) => (resolve = r)))
        render(wrap(<DashboardPage />))
        expect(sessionStorage.getItem("lastViewedMod")).toBe(MOD.id)
        resolve(new Response(JSON.stringify([MOD]), { status: 200 }))
        await screen.findByText("Zerooz Cathy")
        await waitFor(() => expect(sessionStorage.getItem("lastViewedMod")).toBeNull())
        await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "instant", block: "center" }))
    })

    it("shows an error with Retry when the first load fails, and Retry loads the mods", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        const fetchSpy = vi
            .spyOn(globalThis, "fetch")
            .mockResolvedValueOnce(new Response("boom", { status: 500 }))
            .mockResolvedValueOnce(new Response(JSON.stringify([MOD]), { status: 200 }))
        render(wrap(<DashboardPage />))
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load mods: HTTP 500")
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("Zerooz Cathy")).toBeInTheDocument()
        expect(fetchSpy).toHaveBeenCalledTimes(2)
    })

    it("says no mods match when the search hides every card", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([MOD]), { status: 200 }))
        render(wrap(<DashboardPage />))
        await screen.findByText("Zerooz Cathy")
        await userEvent.type(screen.getByPlaceholderText("Search by name or author..."), "zzz")
        expect(screen.getByText('No mods match "zzz".')).toBeInTheDocument()
    })

    it("keeps the cards and shows a dismissible banner when Refresh fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
            Promise.resolve(String(input).endsWith("/mods/refresh") ? new Response("boom", { status: 500 }) : new Response(JSON.stringify([MOD]), { status: 200 }))
        )
        render(wrap(<DashboardPage />))
        await screen.findByText("Zerooz Cathy")
        await userEvent.click(screen.getByRole("button", { name: "Refresh" }))
        expect(await screen.findByText("Refresh failed: HTTP 500")).toBeInTheDocument()
        expect(screen.getByText("Zerooz Cathy")).toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Dismiss" }))
        expect(screen.queryByText("Refresh failed: HTTP 500")).not.toBeInTheDocument()
    })

    it("clears the load error when a Refresh succeeds after a failed first load", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
            Promise.resolve(
                String(input).endsWith("/mods/refresh") ? new Response(`data: ${JSON.stringify({ done: true, results: [MOD] })}\n\n`, { status: 200 }) : new Response("boom", { status: 500 })
            )
        )
        render(wrap(<DashboardPage />))
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load mods: HTTP 500")
        await userEvent.click(screen.getByRole("button", { name: "Refresh" }))
        expect(await screen.findByText("Zerooz Cathy")).toBeInTheDocument()
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })
})
