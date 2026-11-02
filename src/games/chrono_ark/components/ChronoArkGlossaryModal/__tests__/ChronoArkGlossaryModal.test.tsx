import { act, fireEvent, render, screen, waitFor, within } from "@/testUtils"
import { afterEach, describe, expect, it, vi } from "vitest"

import ChronoArkGlossaryModal from "@/games/chrono_ark/components/ChronoArkGlossaryModal"
import type { GlossaryTerm } from "@/lib/types"

const GLOSSARY: Record<string, GlossaryTerm> = {
    罗兰: { english: "Roland", category: "characters", key: "", source_mappings: { Chinese: "罗兰" } },
}

/**
 * Render the modal with spies for every callback.
 *
 * @returns The callback spies.
 */
function renderModal() {
    const props = { onChanged: vi.fn(), onApplied: vi.fn(), onTranslationsChanged: vi.fn(), onRequestDeleteAll: vi.fn(), onSuggestionsChanged: vi.fn(), onClose: vi.fn() }
    render(<ChronoArkGlossaryModal glossary={GLOSSARY} modId="1" strings={[]} {...props} />)
    return props
}

/**
 * Open the Roland row's editor, type a new English and save.
 *
 * @param english The new English to save.
 */
async function editRoland(english: string) {
    const row = screen.getByText("Roland").closest(".glossary-row") as HTMLElement
    fireEvent.click(within(row).getByRole("button", { name: "Edit" }))
    fireEvent.change(screen.getByDisplayValue("Roland"), { target: { value: english } })
    await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Save" }))
    })
}

afterEach(() => {
    vi.restoreAllMocks()
})

describe("ChronoArkGlossaryModal", () => {
    it("PUTs an edit under the old English and reports the translations it renamed", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "success", replaced: 2 })))
        const props = renderModal()

        await editRoland("Rolan")

        const [url, init] = fetchSpy.mock.calls[0]
        expect(String(url)).toMatch(/\/api\/games\/chrono_ark\/mods\/1\/glossary\/Roland$/)
        expect((init as RequestInit).method).toBe("PUT")
        expect(JSON.parse((init as RequestInit).body as string)).toEqual({ english: "Rolan", source_mappings: { Chinese: "罗兰" }, category: "characters" })
        await waitFor(() => expect(screen.getByText("Rolan: updated 2 translations.")).toBeInTheDocument())
        expect(props.onChanged).toHaveBeenCalled()
        expect(props.onTranslationsChanged).toHaveBeenCalled()
    })

    it("does not refresh translations when the edit renamed none", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "success", replaced: 0 })))
        const props = renderModal()

        await editRoland("Roland")

        await waitFor(() => expect(props.onChanged).toHaveBeenCalled())
        expect(props.onTranslationsChanged).not.toHaveBeenCalled()
    })
})
