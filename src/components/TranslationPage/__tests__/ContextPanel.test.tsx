import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ContextPanel } from "@/components/TranslationPage/ContextPanel"

const EMPTY = { source_game: "", character_name: "", background: "" }

describe("ContextPanel", () => {
    it("labels its three fields and saves the edited draft", async () => {
        const onSave = vi.fn().mockResolvedValue(undefined)
        render(<ContextPanel title="Character Context" value={EMPTY} onSave={onSave} />)
        expect(screen.getByRole("heading", { name: "Character Context" })).toBeInTheDocument()
        await userEvent.type(screen.getByLabelText("Source Game"), "Library of Ruina")
        await userEvent.type(screen.getByLabelText("Background"), "A fixer")
        await userEvent.click(screen.getByRole("button", { name: "Save Context" }))
        expect(onSave).toHaveBeenCalledWith({ source_game: "Library of Ruina", character_name: "", background: "A fixer" })
        expect(await screen.findByText("Saved!")).toBeInTheDocument()
    })

    it("keeps an unsaved draft when the parent re-renders with the same saved fields", async () => {
        const { rerender } = render(<ContextPanel title="Mod Context" value={{ ...EMPTY }} onSave={vi.fn()} />)
        await userEvent.type(screen.getByLabelText("Character Name"), "Miaoying")
        // A language change on WH3 hands the panel a new object with the same three fields.
        rerender(<ContextPanel title="Mod Context" value={{ ...EMPTY }} onSave={vi.fn()} />)
        expect(screen.getByLabelText("Character Name")).toHaveValue("Miaoying")
    })

    it("resets the draft when the saved fields change", () => {
        const { rerender } = render(<ContextPanel title="Mod Context" value={EMPTY} onSave={vi.fn()} />)
        rerender(<ContextPanel title="Mod Context" value={{ ...EMPTY, source_game: "WH3" }} onSave={vi.fn()} />)
        expect(screen.getByLabelText("Source Game")).toHaveValue("WH3")
    })

    it("shows the error when saving fails", async () => {
        render(<ContextPanel title="Mod Context" value={EMPTY} onSave={vi.fn().mockRejectedValue(new Error("disk full"))} />)
        await userEvent.click(screen.getByRole("button", { name: "Save Context" }))
        expect(await screen.findByText("disk full")).toBeInTheDocument()
    })

    it("uses game-specific placeholders when given", () => {
        render(<ContextPanel title="Mod Context" value={EMPTY} onSave={vi.fn()} placeholders={{ source_game: "e.g. Total War: Warhammer III" }} />)
        expect(screen.getByLabelText("Source Game")).toHaveAttribute("placeholder", "e.g. Total War: Warhammer III")
        expect(screen.getByLabelText("Character Name")).toHaveAttribute("placeholder", "e.g. Roland")
    })
})
