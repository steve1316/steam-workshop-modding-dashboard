import { render, screen, waitFor } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import SupportedModsPage from "@/games/total_war_warhammer_3/pages/SupportedMods"
import type { ValidationIssue } from "@/games/total_war_warhammer_3/lib/types"

vi.mock("@/games/total_war_warhammer_3/hooks/useValidation", () => ({
    useValidation: vi.fn(),
}))

import { useValidation } from "@/games/total_war_warhammer_3/hooks/useValidation"

afterEach(() => {
    vi.restoreAllMocks()
    vi.resetAllMocks()
})

function defaultHook(overrides: Partial<{ issues: ValidationIssue[] | null; loading: boolean; error: unknown }> = {}) {
    vi.mocked(useValidation).mockReturnValue({
        issues: overrides.issues ?? [],
        loading: overrides.loading ?? false,
        error: (overrides.error ?? null) as never,
        refresh: vi.fn(),
    })
}

function withRouter(ui: React.ReactNode) {
    return <MemoryRouter>{ui}</MemoryRouter>
}

describe("SupportedMods page", () => {
    it("renders fetched mods as a card grid", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ mods: [{ name: "Mod A", package_name: "mod_a", path: "/a", modified_attributes: ["melee"] }] }), { status: 200 }))
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText("Mod A")).toBeInTheDocument())
        expect(screen.getByText("mod_a")).toBeInTheDocument()
    })

    it("filters by search query", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(
                JSON.stringify({
                    mods: [
                        { name: "Apple Mod", package_name: "apple", path: "/a", modified_attributes: [] },
                        { name: "Banana Mod", package_name: "banana", path: "/b", modified_attributes: [] },
                    ],
                }),
                { status: 200 }
            )
        )
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText("Apple Mod")).toBeInTheDocument())
        const search = screen.getByPlaceholderText(/search/i)
        await userEvent.type(search, "banana")
        expect(screen.queryByText("Apple Mod")).not.toBeInTheDocument()
        expect(screen.getByText("Banana Mod")).toBeInTheDocument()
    })

    it("hides the vanilla entry from the card grid", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(
                JSON.stringify({
                    mods: [
                        { name: "Vanilla", package_name: "vanilla", path: "", modified_attributes: [] },
                        { name: "Real Mod", package_name: "pak_real", path: "/path/real.pack", modified_attributes: [] },
                    ],
                }),
                { status: 200 }
            )
        )
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText("Real Mod")).toBeInTheDocument())
        expect(screen.queryByText("Vanilla")).not.toBeInTheDocument()
    })

    it("shows RegistryErrorBanner on 503", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "helper_scripts_path not configured" }), { status: 503 }))
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText(/Helper scripts not configured/i)).toBeInTheDocument())
    })

    it("renders a ValidationBadge in the Status cell when useValidation reports issues for that mod", async () => {
        defaultHook({
            issues: [
                {
                    kind: "missing_mod_path",
                    severity: "error",
                    mod_package_name: "mod_a",
                    mod_name: "Mod A",
                    target: "/fake/a.pack",
                    message: "path '/fake/a.pack' does not exist on disk",
                },
            ],
        })
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(JSON.stringify({ mods: [{ name: "Mod A", package_name: "mod_a", path: "/fake/a.pack", modified_attributes: [] }] }), { status: 200 })
        )
        render(withRouter(<SupportedModsPage />))
        expect(await screen.findByLabelText(/1 validation issue/)).toBeInTheDocument()
    })

    it("renders the validation panel above the grid when useValidation reports issues", async () => {
        defaultHook({
            issues: [
                {
                    kind: "missing_mod_path",
                    severity: "error",
                    mod_package_name: "mod_a",
                    mod_name: "Mod A",
                    target: "/fake/a.pack",
                    message: "path '/fake/a.pack' does not exist on disk",
                },
            ],
        })
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(JSON.stringify({ mods: [{ name: "Mod A", package_name: "mod_a", path: "/fake/a.pack", modified_attributes: [] }] }), { status: 200 })
        )
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText(/missing mod paths \(1\)/i)).toBeInTheDocument())
        expect(screen.getByRole("button", { name: /^refresh$/i })).toBeInTheDocument()
    })

    it("renders no badge when there are no issues for a given mod", async () => {
        defaultHook({ issues: [] })
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ mods: [{ name: "Clean Mod", package_name: "clean", path: "/c", modified_attributes: [] }] }), { status: 200 }))
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText("Clean Mod")).toBeInTheDocument())
        expect(screen.queryByLabelText(/validation issue/)).not.toBeInTheDocument()
    })

    it("shows skeleton cards while the mods load", () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => {}))
        render(withRouter(<SupportedModsPage />))
        expect(screen.getByRole("status", { name: /loading mods/i })).toBeInTheDocument()
    })

    it("puts the search field and + Add Mod in one toolbar row", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ mods: [] }), { status: 200 }))
        render(withRouter(<SupportedModsPage />))
        const toolbar = screen.getByPlaceholderText(/search by name or package_name/i).closest(".dashboard-toolbar")
        expect(toolbar).toContainElement(screen.getByRole("button", { name: "+ Add Mod" }))
        expect(await screen.findByText("No supported mods yet. Use + Add Mod to add one.")).toBeInTheDocument()
    })

    it("says no mods match when the search hides every card", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ mods: [{ name: "Apple Mod", package_name: "apple", path: "/a", modified_attributes: [] }] }), { status: 200 }))
        render(withRouter(<SupportedModsPage />))
        await waitFor(() => expect(screen.getByText("Apple Mod")).toBeInTheDocument())
        await userEvent.type(screen.getByPlaceholderText(/search/i), "zzz")
        expect(screen.getByText('No mods match "zzz".')).toBeInTheDocument()
    })

    it("shows an error with Retry on a network failure, and Retry loads the mods", async () => {
        defaultHook()
        vi.spyOn(globalThis, "fetch")
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(new Response(JSON.stringify({ mods: [{ name: "Mod A", package_name: "mod_a", path: "/a", modified_attributes: [] }] }), { status: 200 }))
        render(withRouter(<SupportedModsPage />))
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load supported mods: Failed to fetch")
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("Mod A")).toBeInTheDocument()
    })
})
