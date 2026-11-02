import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import IgnoredModsPanel, { type IgnoredModInfo } from "@/pages/Settings/IgnoredModsPanel"

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const VIEW_DECK: IgnoredModInfo = {
    id: "3027765042",
    name: "ViewDeck",
    author: "neo",
    preview_image: "/workshop/3027765042/icon.png",
    url: "https://steamcommunity.com/sharedfiles/filedetails/?id=3027765042",
    installed: true,
}
const MISSING: IgnoredModInfo = { id: "3490139439", name: "3490139439", author: "", preview_image: null, url: "https://steamcommunity.com/sharedfiles/filedetails/?id=3490139439", installed: false }

afterEach(() => {
    vi.restoreAllMocks()
})

describe("IgnoredModsPanel", () => {
    it("shows each ignored mod's name, author, cover and install state", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json([VIEW_DECK, MISSING]))
        render(<IgnoredModsPanel mods={[VIEW_DECK.id, MISSING.id]} onChange={vi.fn()} />)
        expect(await screen.findByText("ViewDeck")).toBeInTheDocument()
        expect(screen.getByText("by neo")).toBeInTheDocument()
        expect(screen.getByText("3027765042")).toBeInTheDocument()
        const viewDeckRow = screen.getByText("ViewDeck").closest(".ignored-mod")!
        expect(viewDeckRow.querySelector("img")?.getAttribute("src")).toContain("/workshop/3027765042/icon.png")
        expect(screen.getByRole("link", { name: "Open ViewDeck on Steam" })).toHaveAttribute("href", VIEW_DECK.url)
        expect(screen.getByText("Not installed").closest(".ignored-mod")?.getAttribute("data-mod-id")).toBe(MISSING.id)
        expect(String(fetchSpy.mock.calls[0][0])).toContain("/settings/ignored-mods?ids=3027765042%2C3490139439")
    })

    it("still lists the bare ids when the lookup fails, and removes one", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ detail: "down" }, 500))
        const onChange = vi.fn()
        render(<IgnoredModsPanel mods={["111", "222"]} onChange={onChange} />)
        await vi.waitFor(() => expect(fetchSpy).toHaveBeenCalled())
        expect(screen.getByText("111")).toBeInTheDocument()
        expect(screen.getByText("222")).toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Remove 111" }))
        expect(onChange).toHaveBeenCalledWith(["222"])
    })
})
