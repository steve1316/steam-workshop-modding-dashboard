import { render, screen, fireEvent, waitFor } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import GlossaryPage from "@/games/total_war_warhammer_3/pages/Glossary"

const GLOSSARY = {
    terms: {
        Armour: { english: "Armour", category: "stats", key: "k1", source_mappings: { Chinese: "护甲", Korean: "방어구" } },
        "The Black Pit": { english: "The Black Pit", category: "regions", key: "k2", source_mappings: { Chinese: "黑暗深渊" } },
    },
}

function mockGlossaryFetch() {
    return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(GLOSSARY), { status: 200 }))
}

afterEach(() => {
    vi.restoreAllMocks()
})

describe("WH3 GlossaryPage", () => {
    it("renders fetched terms with their Chinese mapping", async () => {
        mockGlossaryFetch()
        render(<GlossaryPage />)
        expect(await screen.findByText("Armour")).toBeInTheDocument()
        expect(screen.getByText("护甲")).toBeInTheDocument()
        expect(screen.getByText("The Black Pit")).toBeInTheDocument()
    })

    it("filters terms by search text", async () => {
        mockGlossaryFetch()
        render(<GlossaryPage />)
        await screen.findByText("Armour")
        fireEvent.change(screen.getByPlaceholderText("Search terms..."), { target: { value: "black" } })
        await waitFor(() => expect(screen.queryByText("Armour")).not.toBeInTheDocument())
        expect(screen.getByText("The Black Pit")).toBeInTheDocument()
    })

    it("filters terms by category", async () => {
        mockGlossaryFetch()
        render(<GlossaryPage />)
        await screen.findByText("Armour")
        fireEvent.click(screen.getByRole("button", { name: "regions" }))
        await waitFor(() => expect(screen.queryByText("Armour")).not.toBeInTheDocument())
        expect(screen.getByText("The Black Pit")).toBeInTheDocument()
    })

    it("shows a dash when a term has no Korean mapping", async () => {
        mockGlossaryFetch()
        render(<GlossaryPage />)
        await screen.findByText("The Black Pit")
        expect(screen.getByText("—")).toBeInTheDocument()
    })

    it("marks the active category as a game-accent filter pill", async () => {
        mockGlossaryFetch()
        render(<GlossaryPage />)
        await userEvent.click(await screen.findByRole("button", { name: "regions" }))
        expect(screen.getByRole("button", { name: "regions" })).toHaveClass("filter-pill", "btn-primary")
    })

    it("shows an error with Retry when the glossary fails to load, and Retry loads it", async () => {
        vi.spyOn(globalThis, "fetch")
            .mockImplementationOnce(() => Promise.resolve(new Response(JSON.stringify({ detail: "vanilla_text missing" }), { status: 500 })))
            .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(GLOSSARY), { status: 200 })))
        render(<GlossaryPage />)
        expect(await screen.findByRole("alert")).toHaveTextContent("vanilla_text missing")
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("Armour")).toBeInTheDocument()
    })
})
