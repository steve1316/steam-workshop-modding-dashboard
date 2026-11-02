import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import PublishWorkshopDialog from "@/games/total_war_warhammer_3/components/PublishWorkshopDialog"

/**
 * Answer the change-notes request with `body` and `status`, and any other request with an empty object.
 *
 * @param body JSON body returned for `/packs/change-notes`.
 * @param status HTTP status for that response.
 * @returns The fetch spy.
 */
const mockChangeNotes = (body: unknown, status = 200) =>
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
        if (String(input).includes("/packs/change-notes")) return new Response(JSON.stringify(body), { status })
        return new Response("{}", { status: 200 })
    })

const renderDialog = () => render(<PublishWorkshopDialog workshopId="999" title="Mod" onClose={() => {}} />)

afterEach(() => {
    vi.restoreAllMocks()
})

describe("PublishWorkshopDialog changenote", () => {
    it("pre-fills the textarea with the generated note", async () => {
        mockChangeNotes({ notes: { "999": { note: "[u]Translation update[/u]", pending: true, kind: "translation" } }, errors: [] })
        renderDialog()
        await waitFor(() => expect(screen.getByRole("textbox")).toHaveValue("[u]Translation update[/u]"))
    })

    it("shows a generating placeholder while the note loads", () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => {}))
        renderDialog()
        expect(screen.getByPlaceholderText("Generating changenote...")).toBeInTheDocument()
        expect(screen.getByRole("textbox")).not.toBeDisabled()
    })

    it("leaves the box empty and says so when nothing changed since the last upload", async () => {
        mockChangeNotes({ notes: { "999": { note: "old", pending: false, kind: "compat" } }, errors: [] })
        renderDialog()
        expect(await screen.findByText("No changes since the last recorded upload.")).toBeInTheDocument()
        expect(screen.getByRole("textbox")).toHaveValue("")
    })

    it("shows the backend error when no note could be generated", async () => {
        mockChangeNotes({ notes: { "999": null }, errors: ["helper_scripts path is not configured"] })
        renderDialog()
        expect(await screen.findByText("Couldn't generate a changenote: helper_scripts path is not configured")).toBeInTheDocument()
        expect(screen.getByRole("textbox")).toHaveValue("")
    })

    it("shows a neutral message when no note is generated and there are no errors", async () => {
        mockChangeNotes({ notes: { "999": null }, errors: [] })
        renderDialog()
        expect(await screen.findByText("No generated changenote for this pack.")).toBeInTheDocument()
        expect(screen.getByRole("textbox")).toHaveValue("")
    })

    it("shows a warning when the change-notes request fails", async () => {
        mockChangeNotes({ detail: "boom" }, 500)
        renderDialog()
        expect(await screen.findByText("Couldn't generate a changenote: boom")).toBeInTheDocument()
    })

    it("keeps what the user typed while the note was loading", async () => {
        let resolve: (res: Response) => void = () => {}
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>((r) => (resolve = r)))
        renderDialog()
        fireEvent.change(screen.getByRole("textbox"), { target: { value: "my own note" } })
        await act(async () => {
            resolve(new Response(JSON.stringify({ notes: { "999": { note: "generated", pending: true, kind: "compat" } }, errors: [] }), { status: 200 }))
        })
        expect(screen.getByRole("textbox")).toHaveValue("my own note")
    })
})
