import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { GlossaryEditor, type GlossaryEditorTerm } from "@/translation/GlossaryEditor"

const TERMS: GlossaryEditorTerm[] = [
    { english: "Dragon", category: "unit", sourceMappings: { Chinese: "龙" } },
    { english: "Fireball", category: "skill", sourceMappings: { Chinese: "火球" } },
]

describe("GlossaryEditor", () => {
    it("renders terms with their source summary", () => {
        render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        expect(screen.getByText("Dragon")).toBeInTheDocument()
        expect(screen.getByText("Chinese: 龙")).toBeInTheDocument()
    })

    it("adds a per-language term mapping language -> source", async () => {
        const onAdd = vi.fn()
        render(<GlossaryEditor terms={[]} perLanguage languages={["Chinese", "Korean"]} onAdd={onAdd} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        fireEvent.change(screen.getByPlaceholderText("English term"), { target: { value: "Sword" } })
        fireEvent.change(screen.getByPlaceholderText("Source text"), { target: { value: "검" } })
        fireEvent.change(screen.getByDisplayValue("Chinese"), { target: { value: "Korean" } })
        fireEvent.click(screen.getByRole("button", { name: "Add" }))
        expect(onAdd).toHaveBeenCalledWith({ english: "Sword", category: "", sourceMappings: { Korean: "검" } })
    })

    it("adds a single-source term under a flat key when not per-language", async () => {
        const onAdd = vi.fn()
        render(<GlossaryEditor terms={[]} onAdd={onAdd} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        fireEvent.change(screen.getByPlaceholderText("English term"), { target: { value: "Cathay" } })
        fireEvent.change(screen.getByPlaceholderText("Source text"), { target: { value: "震旦" } })
        fireEvent.change(screen.getByPlaceholderText("Category"), { target: { value: "faction" } })
        fireEvent.click(screen.getByRole("button", { name: "Add" }))
        expect(onAdd).toHaveBeenCalledWith({ english: "Cathay", category: "faction", sourceMappings: { source: "震旦" } })
    })

    it("removes a term", () => {
        const onRemove = vi.fn()
        render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={onRemove} />)
        // Two rows -> two Remove buttons; click the first (Dragon, sorted first).
        fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0])
        expect(onRemove).toHaveBeenCalledWith("Dragon")
    })

    it("renders a category dropdown when categoryOptions is provided", () => {
        render(<GlossaryEditor terms={[]} categoryOptions={["custom", "skills"]} onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        expect(screen.getByRole("option", { name: "skills" })).toBeInTheDocument()
    })

    it("renders per-term extra actions via renderRowActions", () => {
        render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} renderRowActions={(t) => <button>Apply {t.english}</button>} />)
        expect(screen.getByRole("button", { name: "Apply Dragon" })).toBeInTheDocument()
    })

    it("lets the term list fill its container when fillHeight is set", () => {
        const { container } = render(
            <GlossaryEditor terms={[{ english: "Roland", category: "characters", sourceMappings: { Chinese: "罗兰" } }]} onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} fillHeight />
        )
        expect(container.firstChild).toHaveClass("glossary-editor", "glossary-editor-fill")
        expect(container.querySelector(".glossary-editor-list")).not.toBeNull()
    })

    it("filters terms by English text and highlights the match", () => {
        const { container } = render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        fireEvent.change(screen.getByPlaceholderText("Search terms..."), { target: { value: "drag" } })
        expect(screen.queryByText("Fireball")).toBeNull()
        expect(container.querySelector("mark.search-highlight")?.textContent).toBe("Drag")
    })

    it("filters terms by source text", () => {
        render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        fireEvent.change(screen.getByPlaceholderText("Search terms..."), { target: { value: "火球" } })
        expect(screen.getByText("Fireball")).toBeInTheDocument()
        expect(screen.queryByText("Dragon")).toBeNull()
    })

    it("shows a no-match message when the search matches nothing", () => {
        render(<GlossaryEditor terms={TERMS} perLanguage onAdd={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />)
        fireEvent.change(screen.getByPlaceholderText("Search terms..."), { target: { value: "zzz" } })
        expect(screen.getByText('No terms match "zzz".')).toBeInTheDocument()
    })
})
