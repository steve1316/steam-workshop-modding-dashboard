import { act, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import DashboardPage from "@/games/total_war_warhammer_3/pages/Dashboard"

afterEach(() => {
    vi.restoreAllMocks()
    vi.resetAllMocks()
})

const wrap = (ui: React.ReactNode) => <MemoryRouter>{ui}</MemoryRouter>

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const MOD_A = {
    workshop_id: "3392058226",
    display_name: "Whc's Cathay translation",
    parent_workshop_ids: ["3380000000"],
    local_source_dir: "",
    source_language: "Chinese",
    target_language: "English",
    preview_image_url: null,
}
const MOD_B = { ...MOD_A, workshop_id: "3315737452", display_name: "Zerooz Cathy translation" }

/**
 * Answers the translation list with `list()`, returns an idle body for everything else, and leaves rescans unanswered.
 *
 * @param list Produces the translation list response for each call.
 */
function mockListOnly(list: () => Promise<Response>) {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        const url = String(input)
        if (url.endsWith("/translation/mods")) return list()
        if (url.endsWith("/rescan")) return new Promise<Response>(() => {})
        return Promise.resolve(json({ status: "idle" }))
    })
}

/**
 * Answers the translation list with `list()`, holds each rescan until released, and returns an idle body for everything else.
 *
 * @param list Produces the translation list response for each call.
 * @returns The held rescans (release in order) and the rescan URLs requested so far.
 */
function mockDashboardFetch(list: () => Promise<Response>) {
    const pendingRescans: Array<() => void> = []
    const rescanCalls: string[] = []
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        const url = String(input)
        if (url.endsWith("/translation/mods")) return list()
        if (url.endsWith("/rescan")) {
            rescanCalls.push(url)
            return new Promise<Response>((resolve) => pendingRescans.push(() => resolve(json({ mod_id: "x", counts: { translated: 1, untranslated: 0, stale: 0, orphan: 0 } }))))
        }
        return Promise.resolve(json({ status: "idle" }))
    })
    return { pendingRescans, rescanCalls }
}

describe("Dashboard page", () => {
    it("renders 6 pack cards", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "idle" }), { status: 200 }))
        render(wrap(<DashboardPage />))
        await waitFor(() => expect(screen.getAllByRole("button", { name: /rebuild/i }).length).toBeGreaterThanOrEqual(6))
    })

    it("keeps a space between the bolded Rebuild and the word button in the about text", () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "idle" }), { status: 200 }))
        render(wrap(<DashboardPage />))
        const about = screen.getByRole("heading", { name: /about the compat packs/i }).nextElementSibling
        expect(about?.textContent).toContain("The Rebuild button regenerates")
    })

    it("shows skeleton cards while the translation mods are loading", () => {
        vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
            if (String(input).includes("/translation/mods")) return new Promise<Response>(() => {})
            return Promise.resolve(new Response(JSON.stringify({ status: "idle" }), { status: 200 }))
        })
        render(wrap(<DashboardPage />))
        expect(screen.getByRole("status", { name: /loading translation mods/i })).toBeInTheDocument()
    })

    it("opens the PublishAllDialog when the Publish All button is clicked", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "idle" }), { status: 200 }))
        const { default: userEvent } = await import("@testing-library/user-event")
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        await user.click(screen.getByRole("button", { name: /^publish all$/i }))
        expect(screen.getByRole("heading", { name: /publish all to workshop/i })).toBeInTheDocument()
    })

    it("disables rebuild buttons when a run is already in progress", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(
                JSON.stringify({
                    status: "running",
                    run_id: "abc",
                    script_id: "update_dynamic_rors",
                    started_at: new Date().toISOString(),
                    lines_emitted: 10,
                }),
                { status: 200 }
            )
        )
        render(wrap(<DashboardPage />))
        await waitFor(() => expect(screen.getAllByRole("button", { name: /run in progress/i }).length).toBeGreaterThanOrEqual(1))
    })

    it("filters pack and translation cards by name as the user types, and Clear brings them back", async () => {
        mockListOnly(() => Promise.resolve(json([MOD_A, MOD_B])))
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        await screen.findByRole("heading", { name: "Whc's Cathay translation" })
        await user.type(screen.getByPlaceholderText("Search by name or workshop ID..."), "velocity")
        expect(screen.getByRole("heading", { name: "Double Projectile Velocity Compat" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "2x Unit Size Compat" })).not.toBeInTheDocument()
        expect(screen.getByText('No translation mods match "velocity".')).toBeInTheDocument()
        await user.click(screen.getByRole("button", { name: "Clear search" }))
        expect(screen.getByRole("heading", { name: "2x Unit Size Compat" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Zerooz Cathy translation" })).toBeInTheDocument()
    })

    it("finds a translation mod by workshop id and says no packs match", async () => {
        mockListOnly(() => Promise.resolve(json([MOD_A, MOD_B])))
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        await screen.findByRole("heading", { name: "Whc's Cathay translation" })
        await user.type(screen.getByPlaceholderText("Search by name or workshop ID..."), "3392058226")
        expect(screen.getByText('No packs match "3392058226".')).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Whc's Cathay translation" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Zerooz Cathy translation" })).not.toBeInTheDocument()
    })

    it("says no translation mods were found when the list is empty", async () => {
        mockListOnly(() => Promise.resolve(json([])))
        render(wrap(<DashboardPage />))
        expect(await screen.findByText("No translation mods found.")).toBeInTheDocument()
    })

    it("shows the intro as a static panel with the standard-size header buttons", () => {
        mockListOnly(() => new Promise<Response>(() => {}))
        render(wrap(<DashboardPage />))
        const intro = screen.getByRole("heading", { name: /about the compat packs/i }).closest(".panel")
        expect(intro).toHaveClass("glass-card", "static")
        expect(screen.getByRole("button", { name: /^publish all$/i })).not.toHaveAttribute("style")
    })

    it("counts through the rescan on open in the Refresh label, then re-enables it", async () => {
        const { pendingRescans, rescanCalls } = mockDashboardFetch(() => Promise.resolve(json([MOD_A, MOD_B])))
        render(wrap(<DashboardPage />))
        expect(await screen.findByRole("button", { name: "Refreshing (1/2)\u2026" })).toBeDisabled()
        await act(async () => pendingRescans.shift()!())
        expect(await screen.findByRole("button", { name: "Refreshing (2/2)\u2026" })).toBeDisabled()
        await act(async () => pendingRescans.shift()!())
        expect(await screen.findByRole("button", { name: "Refresh" })).toBeEnabled()
        expect(rescanCalls).toHaveLength(2)
    })

    it("re-lists and rescans every translation mod when Refresh is clicked", async () => {
        const list = vi.fn(() => Promise.resolve(json([MOD_A])))
        const { pendingRescans, rescanCalls } = mockDashboardFetch(list)
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        await waitFor(() => expect(pendingRescans).toHaveLength(1))
        await act(async () => pendingRescans.shift()!())
        await user.click(await screen.findByRole("button", { name: "Refresh" }))
        await waitFor(() => expect(rescanCalls).toHaveLength(2))
        expect(list).toHaveBeenCalledTimes(2)
    })

    it("shows Retry when the translation list fails to load, and Retry loads it", async () => {
        const list = vi
            .fn()
            .mockImplementationOnce(() => Promise.resolve(json({ detail: "registry unreadable" }, 500)))
            .mockImplementation(() => Promise.resolve(json([MOD_A])))
        mockDashboardFetch(list)
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load translation mods: registry unreadable")
        await user.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByRole("heading", { name: "Whc's Cathay translation" })).toBeInTheDocument()
    })

    it("keeps the cards and shows a dismissible banner when a Refresh cannot list the mods", async () => {
        const list = vi
            .fn()
            .mockImplementationOnce(() => Promise.resolve(json([MOD_A])))
            .mockImplementation(() => Promise.resolve(json({ detail: "registry unreadable" }, 500)))
        const { pendingRescans } = mockDashboardFetch(list)
        const user = userEvent.setup()
        render(wrap(<DashboardPage />))
        await waitFor(() => expect(pendingRescans).toHaveLength(1))
        await act(async () => pendingRescans.shift()!())
        await user.click(await screen.findByRole("button", { name: "Refresh" }))
        expect(await screen.findByText("Could not refresh translation mods: registry unreadable")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Whc's Cathay translation" })).toBeInTheDocument()
        await user.click(screen.getByRole("button", { name: "Dismiss" }))
        expect(screen.queryByText("Could not refresh translation mods: registry unreadable")).not.toBeInTheDocument()
    })

    it("stops rescanning when the user leaves the dashboard", async () => {
        const { pendingRescans, rescanCalls } = mockDashboardFetch(() => Promise.resolve(json([MOD_A, MOD_B])))
        const { unmount } = render(wrap(<DashboardPage />))
        await waitFor(() => expect(rescanCalls).toHaveLength(1))
        unmount()
        await act(async () => pendingRescans.shift()!())
        // Longer than the old 200ms stagger between rescans, so a leftover timer would have fired by now.
        await new Promise((resolve) => setTimeout(resolve, 300))
        expect(rescanCalls).toHaveLength(1)
    })

    it("scrolls back to the translation mod the user opened", async () => {
        const scrollIntoView = vi.fn()
        Element.prototype.scrollIntoView = scrollIntoView
        sessionStorage.setItem("lastViewedMod", MOD_B.workshop_id)
        mockListOnly(() => Promise.resolve(json([MOD_A, MOD_B])))
        render(wrap(<DashboardPage />))
        await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "instant", block: "center" }))
        expect(sessionStorage.getItem("lastViewedMod")).toBeNull()
        Reflect.deleteProperty(Element.prototype, "scrollIntoView")
    })

    it("tells the user when some translation mods could not be rescanned", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
            const url = String(input)
            if (url.endsWith("/translation/mods")) return Promise.resolve(json([MOD_A, MOD_B]))
            if (url.endsWith(`/${MOD_A.workshop_id}/rescan`)) return Promise.resolve(json({ detail: "parent folder missing" }, 500))
            if (url.endsWith("/rescan")) return Promise.resolve(json({ mod_id: "x", counts: { translated: 1, untranslated: 0, stale: 0, orphan: 0 } }))
            return Promise.resolve(json({ status: "idle" }))
        })
        render(wrap(<DashboardPage />))
        expect(await screen.findByText("Could not rescan 1 translation mod.")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Zerooz Cathy translation" })).toBeInTheDocument()
    })

    it("lets the Tabletop Caps compat pack be rebuilt from its card", async () => {
        mockListOnly(() => new Promise<Response>(() => {}))
        render(wrap(<DashboardPage />))
        const card = screen.getByRole("heading", { name: "Tabletop Caps - Yet Another Compatibility Megapack" }).closest(".mod-card") as HTMLElement
        await waitFor(() => expect(within(card).getByRole("button", { name: "Rebuild" })).toBeEnabled())
    })
})
