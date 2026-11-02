import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import GlossaryPage from "@/games/chrono_ark/pages/Glossary"

const GLOSSARY = {
    terms: {
        Barrier: { english: "Barrier", category: "skill", key: "Skill_Barrier", source_file: "Skill.csv", source_mappings: { Korean: "보호막" } },
        Roland: { english: "Roland", category: "character", key: "", source_mappings: {} },
    },
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

afterEach(() => {
    vi.restoreAllMocks()
})

describe("Chrono Ark GlossaryPage", () => {
    it("renders the source file link, key and source mappings, with a dash for missing values", async () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(json(GLOSSARY)))
        render(<GlossaryPage />)
        expect(await screen.findByRole("link", { name: "Skill.csv" })).toBeInTheDocument()
        expect(screen.getByText("Skill_Barrier")).toBeInTheDocument()
        expect(screen.getByText("보호막")).toBeInTheDocument()
        expect(screen.getAllByText("—")).toHaveLength(2)
    })

    it("asks the backend to open the base-game file when its link is clicked", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(json(GLOSSARY)))
        render(<GlossaryPage />)
        await userEvent.click(await screen.findByRole("link", { name: "Skill.csv" }))
        const openCall = fetchSpy.mock.calls.find(([url]) => String(url).endsWith("/open-base-game-file/Skill.csv"))
        expect((openCall?.[1] as RequestInit | undefined)?.method).toBe("POST")
    })

    it("shows an error with Retry when the glossary request fails", async () => {
        vi.spyOn(globalThis, "fetch")
            .mockImplementationOnce(() => Promise.resolve(json({ detail: "boom" }, 500)))
            .mockImplementation(() => Promise.resolve(json(GLOSSARY)))
        render(<GlossaryPage />)
        expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 500")
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("Barrier")).toBeInTheDocument()
    })
})
