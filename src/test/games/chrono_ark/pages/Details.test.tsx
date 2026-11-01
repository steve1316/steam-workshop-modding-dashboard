import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import ModDetail from "../../../../games/chrono_ark/pages/Details"

const MOD_ID = "2945863327"

const STRING = {
    key: "Buff/B_Roland_2_S_Name",
    type: "Text",
    desc: "",
    source: "琅琊工坊",
    source_lang: "Chinese",
    english: "Mook Workshop",
    is_translated: true,
    original_english: "Ranga Workshop",
    is_synced: false,
    is_untouched: false,
    translated_by: "claude",
    source_file: "LangDataDB.csv",
    untranslatable_reason: "",
}

const SUGGESTION = { english: "Roland", source: "罗兰", source_lang: "Chinese", category: "characters", reason: "Recurring name" }

/** Per-test overrides for the faked backend. */
interface Backend {
    /** Body returned by GET export-status. */
    exportStatus?: { has_changes: boolean; has_previous_sync?: boolean }
    /** Pending suggestions returned by GET glossary/suggestions, in order of calls (last one repeats). */
    suggestions?: (typeof SUGGESTION)[][]
    /** Number reported by POST glossary/suggestions/scan. */
    scanNew?: number
    /** HTTP status for GET /mods/{id}. Defaults to 200. */
    modStatus?: number
    /** Provider returned by GET /settings. Defaults to "claude". */
    provider?: string
    /** Rows returned by GET /mods/{id}. Defaults to the one translated `STRING`. */
    strings?: (typeof STRING)[]
}

/**
 * Install a fetch mock that routes the Details page's requests by URL and method.
 *
 * @param backend Per-test overrides for the faked backend.
 * @returns The fetch spy, for asserting on calls.
 */
function mockBackend(backend: Backend = {}) {
    const suggestionQueue = [...(backend.suggestions ?? [[]])]
    const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        if (url.endsWith("/settings")) return json({ provider: backend.provider ?? "claude" })
        if (url.endsWith(`/mods/${MOD_ID}`))
            return backend.modStatus && backend.modStatus !== 200
                ? Promise.resolve(new Response(JSON.stringify({ detail: "Mod not found" }), { status: backend.modStatus }))
                : json({ strings: backend.strings ?? [STRING], name: "Roland", author: "Author", preview_image: null, url: null })
        if (url.endsWith("/export-status")) return json(backend.exportStatus ?? { has_changes: true, has_previous_sync: true })
        if (url.endsWith("/glossary/suggestions/scan") && method === "POST") return json({ status: "success", new: backend.scanNew ?? 0 })
        if (url.endsWith("/glossary/suggestions")) return json(suggestionQueue.length > 1 ? suggestionQueue.shift() : suggestionQueue[0])
        if (url.endsWith("/glossary")) return json({ terms: { Roland: { category: "characters", source_mappings: { Chinese: "罗兰" } } } })
        if (url.endsWith("/character-context")) return json(method === "POST" ? { status: "saved" } : { source_game: "", character_name: "", background: "" })
        if (url.includes("/export") && method === "POST") return json({ applied: 1, files_written: ["LangDataDB.csv"] })
        return json({})
    })
}

/**
 * Render the Details page at its real route.
 *
 * @returns The render result.
 */
function renderPage() {
    return render(
        <MemoryRouter initialEntries={[`/translation/${MOD_ID}`]}>
            <Routes>
                <Route path="/translation/:modId" element={<ModDetail />} />
            </Routes>
        </MemoryRouter>
    )
}

afterEach(() => {
    vi.restoreAllMocks()
})

describe("Chrono Ark Details page", () => {
    it("renders the standard toolbar", async () => {
        mockBackend()
        renderPage()
        await screen.findByText("Mook Workshop")
        for (const name of [/^Mod Glossary/, /^Scan for Terms$/, /^API Responses$/, /^Character Context$/, /^History$/, /^Reset$/, /^Clear English$/, /^Translate \(/]) {
            expect(screen.getByRole("button", { name })).toBeInTheDocument()
        }
        expect(screen.getByRole("button", { name: /Sync Changes/ })).toBeEnabled()
    })

    it("shows a Suggestions button with the pending count", async () => {
        mockBackend({ suggestions: [[SUGGESTION]] })
        renderPage()
        const button = await screen.findByRole("button", { name: /Suggestions/ })
        expect(button).toHaveTextContent("1")
    })

    it("scans for terms, reports the result in a banner, and refreshes suggestions", async () => {
        const fetchSpy = mockBackend({ suggestions: [[], [SUGGESTION]], scanNew: 1 })
        renderPage()
        await screen.findByText("Mook Workshop")
        await userEvent.click(screen.getByRole("button", { name: /^Scan for Terms$/ }))
        expect(await screen.findByText(/Found 1 new glossary term suggestion/)).toBeInTheDocument()
        expect(await screen.findByRole("button", { name: /Suggestions/ })).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([url, init]) => String(url).endsWith("/glossary/suggestions/scan") && init?.method === "POST")).toBe(true)
    })

    it("labels Sync as Re-sync when there are no changes but a previous sync exists", async () => {
        mockBackend({ exportStatus: { has_changes: false, has_previous_sync: true } })
        renderPage()
        expect(await screen.findByRole("button", { name: /Re-sync Changes/ })).toBeEnabled()
    })

    it("disables Sync when there are no changes and no previous sync", async () => {
        mockBackend({ exportStatus: { has_changes: false, has_previous_sync: false } })
        renderPage()
        await screen.findByText("Mook Workshop")
        await waitFor(() => expect(screen.getByRole("button", { name: /Sync Changes/ })).toBeDisabled())
    })

    it("confirms before syncing and then exports", async () => {
        const fetchSpy = mockBackend()
        renderPage()
        await screen.findByText("Mook Workshop")
        await userEvent.click(screen.getByRole("button", { name: /Sync Changes/ }))
        const dialog = screen.getByRole("dialog", { name: "Sync Changes" })
        expect(dialog).toHaveTextContent(/This will overwrite the mod's localization files/)
        await userEvent.click(within(dialog).getByRole("button", { name: /^Sync$/ }))
        expect(await screen.findByText(/Synced 1 translation/)).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([url, init]) => String(url).endsWith(`/mods/${MOD_ID}/export`) && init?.method === "POST")).toBe(true)
    })

    it("toggles the Character Context panel and saves its fields", async () => {
        const fetchSpy = mockBackend()
        renderPage()
        await screen.findByText("Mook Workshop")
        await userEvent.click(screen.getByRole("button", { name: /^Character Context$/ }))
        await userEvent.type(await screen.findByPlaceholderText("e.g. Library of Ruina"), "Library of Ruina")
        await userEvent.click(screen.getByRole("button", { name: /^Save Context$/ }))
        await waitFor(() => {
            const call = fetchSpy.mock.calls.find(([url, init]) => String(url).endsWith("/character-context") && init?.method === "POST")
            expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ source_game: "Library of Ruina" })
        })
    })

    it("opens the mod glossary in a large dialog", async () => {
        mockBackend()
        renderPage()
        await screen.findByText("Mook Workshop")
        await userEvent.click(screen.getByRole("button", { name: /^Mod Glossary/ }))
        const dialog = await screen.findByRole("dialog", { name: "Mod Glossary" })
        expect(dialog).toHaveClass("dialog-xl")
        expect(within(dialog).getByText("Roland")).toBeInTheDocument()
    })

    it("shows a not-found state with a way back when the mod does not exist", async () => {
        mockBackend({ modStatus: 404 })
        renderPage()
        expect(await screen.findByRole("heading", { name: "Mod not found" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Back to Dashboard" })).toBeInTheDocument()
    })

    it("keeps the page when the refresh after a sync fails", async () => {
        const fetchSpy = mockBackend()
        const base = fetchSpy.getMockImplementation()!
        let modLoads = 0
        fetchSpy.mockImplementation((input, init) => {
            if (String(input).endsWith(`/mods/${MOD_ID}`) && ++modLoads > 1) return Promise.resolve(new Response("{}", { status: 500 }))
            return base(input, init)
        })
        renderPage()
        await screen.findByText("Mook Workshop")
        await userEvent.click(screen.getByRole("button", { name: /Sync Changes/ }))
        await userEvent.click(within(screen.getByRole("dialog", { name: "Sync Changes" })).getByRole("button", { name: /^Sync$/ }))
        expect(await screen.findByText(/Synced 1 translation/)).toBeInTheDocument()
        await waitFor(() => expect(modLoads).toBeGreaterThan(1))
        expect(screen.queryByRole("heading", { name: "Could not load this mod" })).not.toBeInTheDocument()
        expect(screen.getByText("Mook Workshop")).toBeInTheDocument()
    })

    it("steps through missing rows by hand when the provider is Manual", async () => {
        const missing = { ...STRING, key: "Character/Roland_Name", source: "罗兰", english: "", is_translated: false, original_english: "", translated_by: "" }
        const description = { ...STRING, key: "Character/Roland_Description", source: "图书馆的客人", english: "A guest of the Library", is_synced: true }
        const fetchSpy = mockBackend({ provider: "manual", strings: [missing, description] })
        renderPage()
        await userEvent.click(await screen.findByRole("button", { name: "Translate (Manual)" }))
        const dialog = await screen.findByRole("dialog", { name: "Manual Translation" })
        expect(within(dialog).getByText("1 of 1")).toBeInTheDocument()
        expect(within(dialog).getByText("A guest of the Library")).toBeInTheDocument()
        await userEvent.click(within(dialog).getByRole("button", { name: "Use" }))
        await userEvent.type(within(dialog).getByRole("textbox"), "{Control>}{Enter}{/Control}")
        expect(await within(dialog).findByText(/Saved 1 of 1/)).toBeInTheDocument()
        const call = fetchSpy.mock.calls.find(([url, init]) => String(url).endsWith(`/mods/${MOD_ID}/strings`) && init?.method === "POST")
        expect(JSON.parse(String(call?.[1]?.body))).toEqual({ key: "Character/Roland_Name", english: "Roland" })
        expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/translate/preview"))).toBe(false)
    })

    it("reports nothing to do in Manual mode when no rows are missing", async () => {
        mockBackend({ provider: "manual" })
        renderPage()
        await userEvent.click(await screen.findByRole("button", { name: "Translate (Manual)" }))
        expect(await screen.findByText("All strings are already translated.")).toBeInTheDocument()
        expect(screen.queryByRole("dialog", { name: "Manual Translation" })).not.toBeInTheDocument()
    })
})
