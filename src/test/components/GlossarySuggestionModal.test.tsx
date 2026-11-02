import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import GlossarySuggestionModal from "@/components/GlossarySuggestionModal"
import type { TermSuggestion } from "@/shared_types"

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
    mockFetch.mockReset()
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) })
})

const SUGGESTIONS: TermSuggestion[] = [{ english: "Roland", source: "롤랑", source_lang: "Korean", category: "characters", reason: "recurring name" }]

describe("GlossarySuggestionModal", () => {
    it("routes accept calls through the provided gameId", async () => {
        render(<GlossarySuggestionModal gameId="total_war_warhammer_3" modId="m1" suggestions={SUGGESTIONS} onClose={vi.fn()} onUpdated={vi.fn()} />)
        fireEvent.click(screen.getByRole("button", { name: /Accept All/ }))
        await waitFor(() => expect(mockFetch).toHaveBeenCalled())
        const acceptCall = mockFetch.mock.calls.find((call) => typeof call[0] === "string" && call[0].includes("/glossary/suggestions/accept"))
        expect(acceptCall).toBeTruthy()
        expect(String(acceptCall![0])).toContain("/games/total_war_warhammer_3/mods/m1/glossary/suggestions/accept")
    })

    /**
     * Find the body of the accept request.
     *
     * @returns The parsed JSON body sent to the accept endpoint.
     */
    function acceptBody() {
        const call = mockFetch.mock.calls.find((c) => String(c[0]).includes("/glossary/suggestions/accept"))
        return JSON.parse(String((call![1] as RequestInit).body))
    }

    /**
     * Edit a suggestion's English and confirm with Enter.
     *
     * @param english The suggestion's current English.
     * @param source The suggestion's source text, used in the text box's name.
     * @param next The new English to type.
     */
    function editTerm(english: string, source: string, next: string) {
        fireEvent.click(screen.getByRole("button", { name: `Edit ${english}` }))
        const box = screen.getByRole("textbox", { name: `English for ${source}` })
        fireEvent.change(box, { target: { value: next } })
        fireEvent.keyDown(box, { key: "Enter" })
    }

    it("accepts a suggestion under its edited English and shows what it replaced", async () => {
        render(<GlossarySuggestionModal gameId="total_war_warhammer_3" modId="m1" suggestions={SUGGESTIONS} onClose={vi.fn()} onUpdated={vi.fn()} />)
        editTerm("Roland", "롤랑", "Rolland")

        expect(screen.getByText("Rolland")).toBeInTheDocument()
        expect(screen.getByTestId("suggestion-was")).toHaveTextContent("was Roland")
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /^Accept$/ }))
        await waitFor(() => expect(mockFetch).toHaveBeenCalled())
        expect(acceptBody()).toEqual({ terms: ["Roland"], renames: { Roland: "Rolland" } })
    })

    it("reports how many translations an edited accept renamed and tells the page to reload them", async () => {
        mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: "success", accepted: 1, replaced: 7 }) })
        const onTranslationsChanged = vi.fn()
        render(<GlossarySuggestionModal gameId="chrono_ark" modId="m1" suggestions={SUGGESTIONS} onClose={vi.fn()} onUpdated={vi.fn()} onTranslationsChanged={onTranslationsChanged} />)
        editTerm("Roland", "롤랑", "Rolland")
        fireEvent.click(screen.getByRole("button", { name: /^Accept$/ }))

        expect(await screen.findByText("Rolland: updated 7 translations.")).toBeInTheDocument()
        expect(onTranslationsChanged).toHaveBeenCalledTimes(1)
    })

    it("cancels an edit with Escape without closing the dialog", () => {
        const onClose = vi.fn()
        render(<GlossarySuggestionModal gameId="chrono_ark" modId="m1" suggestions={SUGGESTIONS} onClose={onClose} onUpdated={vi.fn()} />)
        fireEvent.click(screen.getByRole("button", { name: "Edit Roland" }))
        const box = screen.getByRole("textbox", { name: "English for 롤랑" })
        fireEvent.change(box, { target: { value: "Rolland" } })
        fireEvent.keyDown(box, { key: "Escape" })

        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
        expect(screen.getByText("Roland")).toBeInTheDocument()
        expect(screen.queryByTestId("suggestion-was")).not.toBeInTheDocument()
        expect(onClose).not.toHaveBeenCalled()
    })

    it("keeps the suggested English when an edit is left blank or unchanged", async () => {
        render(<GlossarySuggestionModal gameId="chrono_ark" modId="m1" suggestions={SUGGESTIONS} onClose={vi.fn()} onUpdated={vi.fn()} />)
        editTerm("Roland", "롤랑", "   ")
        expect(screen.queryByTestId("suggestion-was")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /^Accept$/ }))
        await waitFor(() => expect(mockFetch).toHaveBeenCalled())
        expect(acceptBody()).toEqual({ terms: ["Roland"] })
    })

    it("sends only the edited suggestions as renames on Accept All", async () => {
        const two: TermSuggestion[] = [...SUGGESTIONS, { english: "Nangao", source: "南皋", source_lang: "Chinese", category: "location", reason: "place" }]
        render(<GlossarySuggestionModal gameId="total_war_warhammer_3" modId="m1" suggestions={two} onClose={vi.fn()} onUpdated={vi.fn()} />)
        editTerm("Nangao", "南皋", "Nangau")
        fireEvent.click(screen.getByRole("button", { name: /Accept All/ }))
        await waitFor(() => expect(mockFetch).toHaveBeenCalled())
        expect(acceptBody()).toEqual({ terms: ["Roland", "Nangao"], renames: { Nangao: "Nangau" } })
    })
})
