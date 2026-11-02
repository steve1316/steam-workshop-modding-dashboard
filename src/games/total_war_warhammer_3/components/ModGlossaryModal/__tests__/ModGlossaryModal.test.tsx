import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ModGlossaryModal from "@/games/total_war_warhammer_3/components/ModGlossaryModal"

const GLOSSARY = {
    Phoenix: { source: "凤", category: "factions" },
    Cathay: { source: "震旦", category: "factions" },
    Sky: { source: "天", category: "lore_terms" },
}

function mockJson(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status })
}

beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJson(GLOSSARY))
})

afterEach(() => {
    vi.restoreAllMocks()
})

describe("ModGlossaryModal", () => {
    it("loads and lists entries grouped by category", async () => {
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await waitFor(() => screen.getByText("Phoenix"))
        expect(screen.getByText("Cathay")).toBeInTheDocument()
        expect(screen.getByText("Sky")).toBeInTheDocument()
        expect(screen.getByText("factions")).toBeInTheDocument()
        expect(screen.getByText("lore_terms")).toBeInTheDocument()
    })

    it("POSTs a new entry when Add is clicked", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok" })) // POST
        fetchSpy.mockResolvedValueOnce(mockJson({ ...GLOSSARY, Dragon: { source: "龙", category: "factions" } })) // refresh

        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await waitFor(() => screen.getByText("Phoenix"))

        fireEvent.change(screen.getByPlaceholderText(/English term/i), { target: { value: "Dragon" } })
        fireEvent.change(screen.getByPlaceholderText(/Source/i), { target: { value: "龙" } })
        fireEvent.change(screen.getByPlaceholderText(/Category/i), { target: { value: "factions" } })

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /^Add$/ }))
        })

        await waitFor(() => expect(screen.getByText("Dragon")).toBeInTheDocument())
    })

    it("DELETEs an entry when Delete is clicked", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok" })) // DELETE
        const { Phoenix, ...rest } = GLOSSARY
        void Phoenix
        fetchSpy.mockResolvedValueOnce(mockJson(rest)) // refresh

        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await waitFor(() => screen.getByText("Phoenix"))

        const phoenixRow = screen.getByText("Phoenix").closest(".glossary-row") as HTMLElement
        await act(async () => {
            fireEvent.click(within(phoenixRow).getByRole("button", { name: /Remove/i }))
        })
        fireEvent.click(within(await screen.findByRole("dialog", { name: "Remove glossary term" })).getByRole("button", { name: "Remove" }))
        await waitFor(() => expect(screen.queryByText("Phoenix")).not.toBeInTheDocument())
    })

    it("PUTs an updated entry when Save is clicked in edit mode", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok" })) // PUT
        fetchSpy.mockResolvedValueOnce(mockJson({ ...GLOSSARY, "Phoenix Lord": { source: "凤", category: "factions" } })) // refresh

        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await waitFor(() => screen.getByText("Phoenix"))

        const phoenixRow = screen.getByText("Phoenix").closest(".glossary-row") as HTMLElement
        fireEvent.click(within(phoenixRow).getByRole("button", { name: /Edit/i }))

        const englishInput = screen.getByDisplayValue("Phoenix")
        fireEvent.change(englishInput, { target: { value: "Phoenix Lord" } })

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /^Save$/ }))
        })
        await waitFor(() => expect(screen.getByText("Phoenix Lord")).toBeInTheDocument())

        const [, init] = fetchSpy.mock.calls[1]
        expect((init as RequestInit).method).toBe("PUT")
        expect(JSON.parse((init as RequestInit).body as string).english).toBe("Phoenix Lord")
    })

    it("reports and reloads the translations an edited English renamed", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "ok", replaced: 3 })) // PUT
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY)) // refresh
        const onTranslationsChanged = vi.fn()

        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} onTranslationsChanged={onTranslationsChanged} />)
        await waitFor(() => screen.getByText("Phoenix"))
        const phoenixRow = screen.getByText("Phoenix").closest(".glossary-row") as HTMLElement
        fireEvent.click(within(phoenixRow).getByRole("button", { name: /Edit/i }))
        fireEvent.change(screen.getByDisplayValue("Phoenix"), { target: { value: "Phoenix Lord" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /^Save$/ }))
        })

        await waitFor(() => expect(screen.getByText("Phoenix Lord: updated 3 translations.")).toBeInTheDocument())
        expect(onTranslationsChanged).toHaveBeenCalled()
    })

    it("saves suggested edits for review and reports how many were added", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ status: "success", new: 2 }))
        const onSuggestionsChanged = vi.fn()
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={onSuggestionsChanged} />)
        await waitFor(() => screen.getByText("Phoenix"))
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /Suggest edits/i }))
        })
        await waitFor(() => expect(onSuggestionsChanged).toHaveBeenCalledWith(2))
        expect(screen.getByText(/Added 2 edit suggestion\(s\)/)).toBeInTheDocument()
        expect(String(fetchSpy.mock.calls[1][0])).toMatch(/\/api\/games\/total_war_warhammer_3\/mods\/123\/glossary\/suggest-edits$/)
    })

    it("opens as the large glossary dialog", async () => {
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        expect(await screen.findByRole("dialog", { name: "Mod Glossary" })).toHaveClass("dialog-xl", "dialog-fill")
    })

    it("Apply All POSTs old + new english", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        fetchSpy.mockResolvedValueOnce(mockJson(GLOSSARY))
        fetchSpy.mockResolvedValueOnce(mockJson({ replaced: 5 }))

        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await waitFor(() => screen.getByText("Phoenix"))

        fireEvent.click(screen.getByRole("button", { name: /Apply all/i }))
        fireEvent.change(screen.getByPlaceholderText(/Old English/i), { target: { value: "Phoenix" } })
        fireEvent.change(screen.getByPlaceholderText(/New English/i), { target: { value: "Phoenix Lord" } })

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: /^Apply$/ }))
        })
        await waitFor(() => screen.getByText(/Renamed in 5 translations/))
    })

    it("deletes every term after confirming, and shows the empty glossary", async () => {
        let deleted = false
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
            if (init?.method === "DELETE" && String(input).endsWith("/translation/mods/123/glossary")) {
                deleted = true
                return Promise.resolve(mockJson({ status: "success", deleted: 3 }))
            }
            return Promise.resolve(mockJson(deleted ? {} : GLOSSARY))
        })
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await screen.findByText("Phoenix")
        fireEvent.click(screen.getByRole("button", { name: "Delete All" }))
        const dialog = await screen.findByRole("dialog", { name: "Delete All Glossary Terms" })
        expect(dialog).toHaveTextContent("Delete all 3 glossary term(s)?")
        fireEvent.click(within(dialog).getByRole("button", { name: "Delete All" }))
        await waitFor(() => expect(screen.queryByText("Phoenix")).not.toBeInTheDocument())
        expect(screen.getByText("No glossary entries yet.")).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([url, init]) => String(url).endsWith("/translation/mods/123/glossary") && init?.method === "DELETE")).toBe(true)
    })

    it("keeps every term when Delete All is cancelled", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(mockJson(GLOSSARY)))
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await screen.findByText("Phoenix")
        fireEvent.click(screen.getByRole("button", { name: "Delete All" }))
        const dialog = await screen.findByRole("dialog", { name: "Delete All Glossary Terms" })
        fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }))
        await waitFor(() => expect(screen.queryByRole("dialog", { name: "Delete All Glossary Terms" })).not.toBeInTheDocument())
        expect(screen.getByText("Phoenix")).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false)
    })

    it("hides Delete All while the glossary is empty", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(mockJson({})))
        render(<ModGlossaryModal workshopId="123" onClose={vi.fn()} onSuggestionsChanged={vi.fn()} />)
        await screen.findByText("No glossary entries yet.")
        expect(screen.queryByRole("button", { name: "Delete All" })).not.toBeInTheDocument()
    })
})
