import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import GlossaryBrowser, { type GlossaryColumn } from "@/components/GlossaryBrowser"
import type { Glossary } from "@/lib/types"

const GLOSSARY: Glossary = {
    terms: {
        Armour: { english: "Armour", category: "stats", key: "k1", source_mappings: { Chinese: "护甲" } },
        "The Black Pit": { english: "The Black Pit", category: "regions", key: "k2", source_mappings: { Chinese: "黑暗深渊" } },
    },
}

const COLUMNS: GlossaryColumn[] = [{ header: "Chinese", className: "cell-dim", render: (_key, term) => term.source_mappings.Chinese || "—" }]

describe("GlossaryBrowser", () => {
    it("shows the loading state, then the term count, a pill per category and the table", async () => {
        render(<GlossaryBrowser gameId="test_game" load={() => Promise.resolve(GLOSSARY)} englishWidth={200} categoryWidth={120} columns={COLUMNS} />)
        expect(screen.getByText("Loading glossary...")).toBeInTheDocument()
        expect(await screen.findByText("2 base game terms across 2 categories")).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 1, name: "Terminology Glossary" })).toBeInTheDocument()
        for (const name of ["All", "regions", "stats"]) expect(screen.getByRole("button", { name })).toBeInTheDocument()
        expect(screen.getByRole("columnheader", { name: "Chinese" })).toBeInTheDocument()
        expect(screen.getByText("护甲")).toBeInTheDocument()
    })

    it("marks the active category as a game-accent filter pill", async () => {
        render(<GlossaryBrowser gameId="test_game" load={() => Promise.resolve(GLOSSARY)} englishWidth={200} categoryWidth={120} columns={COLUMNS} />)
        await userEvent.click(await screen.findByRole("button", { name: "regions" }))
        expect(screen.getByRole("button", { name: "regions" })).toHaveClass("filter-pill", "btn-primary")
        expect(screen.getByRole("button", { name: "All" })).toHaveClass("filter-pill", "btn-outline")
        expect(screen.queryByText("Armour")).not.toBeInTheDocument()
    })

    it("says no terms match when search and category leave nothing, and clearing the search brings rows back", async () => {
        render(<GlossaryBrowser gameId="test_game" load={() => Promise.resolve(GLOSSARY)} englishWidth={200} categoryWidth={120} columns={COLUMNS} />)
        await userEvent.click(await screen.findByRole("button", { name: "regions" }))
        await userEvent.type(screen.getByPlaceholderText("Search terms..."), "armour")
        expect(screen.getByText("No matching terms found.")).toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Clear search" }))
        expect(screen.getByText("The Black Pit")).toBeInTheDocument()
    })

    it("shows an error with Retry when the glossary fails to load, and Retry loads it", async () => {
        const load = vi.fn<() => Promise<Glossary>>().mockRejectedValueOnce(new Error("HTTP 500")).mockResolvedValue(GLOSSARY)
        render(<GlossaryBrowser gameId="test_game" load={load} englishWidth={200} categoryWidth={120} columns={COLUMNS} />)
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the glossary")
        expect(screen.queryByText(/base game terms/)).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("Armour")).toBeInTheDocument()
        expect(load).toHaveBeenCalledTimes(2)
    })
})
