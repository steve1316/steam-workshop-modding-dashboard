import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import SupportedModFormPage from "@/games/total_war_warhammer_3/pages/SupportedModForm"
import { emptyBasicsState } from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/basicsState"

afterEach(() => {
    vi.restoreAllMocks()
    vi.resetAllMocks()
})

function renderForm(path: string) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/supported-mods/new" element={<SupportedModFormPage />} />
                <Route path="/supported-mods/edit/:packageName" element={<SupportedModFormPage />} />
                <Route path="/supported-mods" element={<div>Mods list page</div>} />
            </Routes>
        </MemoryRouter>
    )
}

describe("SupportedModFormPage", () => {
    it("renders the Basics section with empty fields in add mode", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
        renderForm("/supported-mods/new")
        expect(await screen.findByLabelText(/^Name/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/Package name/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/Workshop ID/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /Save/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete/i })).not.toBeInTheDocument()
    })

    it("renders a Delete button and confirms before firing DELETE in edit mode", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
            const u = url.toString()
            if (u.endsWith("/supported-effects")) {
                return Promise.resolve(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
            }
            if (u.endsWith("/supported-mods") && (!init || init.method !== "POST")) {
                return Promise.resolve(new Response(JSON.stringify({ mods: [{ name: "Target", package_name: "target.pack", path: "", workshop_id: null, modified_attributes: [] }] }), { status: 200 }))
            }
            if (u.endsWith("/supported-mods/target.pack") && init?.method === "DELETE") {
                return Promise.resolve(new Response(JSON.stringify({ mods: [] }), { status: 200 }))
            }
            return Promise.resolve(new Response("{}", { status: 200 }))
        })
        renderForm("/supported-mods/edit/target.pack")
        await waitFor(() => expect(screen.getByDisplayValue("Target")).toBeInTheDocument())
        await userEvent.click(screen.getByRole("button", { name: /Delete/i }))
        // Confirm modal appears - click its primary confirm button.
        await userEvent.click(await screen.findByRole("button", { name: /Confirm/i }))
        await waitFor(() => {
            const deleteCall = fetchSpy.mock.calls.find(([url, init]) => url.toString().endsWith("/supported-mods/target.pack") && (init as RequestInit | undefined)?.method === "DELETE")
            expect(deleteCall).toBeTruthy()
        })
    })

    it("posts the form to /supported-mods on Save in add mode", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
            const u = url.toString()
            if (u.endsWith("/supported-effects")) {
                return Promise.resolve(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
            }
            if (u.endsWith("/supported-mods") && init?.method === "POST") {
                return Promise.resolve(new Response(JSON.stringify({ mods: [] }), { status: 200 }))
            }
            return Promise.resolve(new Response("{}", { status: 200 }))
        })
        renderForm("/supported-mods/new")
        await userEvent.type(await screen.findByLabelText(/^Name/i), "My Mod")
        await userEvent.type(screen.getByLabelText(/Package name/i), "my_mod.pack")
        await userEvent.type(screen.getByLabelText(/Workshop ID/i), "12345")
        await userEvent.click(screen.getByRole("button", { name: /Save/i }))
        await waitFor(() => {
            const postCall = fetchSpy.mock.calls.find(([url, init]) => url.toString().endsWith("/supported-mods") && (init as RequestInit | undefined)?.method === "POST")
            expect(postCall).toBeTruthy()
            const body = JSON.parse(((postCall![1] as RequestInit).body as string) ?? "{}")
            expect(body.entry.name).toBe("My Mod")
            expect(body.entry.package_name).toBe("my_mod.pack")
            expect(body.entry.workshop_id).toBe("12345")
        })
    })

    it("renders the five sections as named panel groups", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
        renderForm("/supported-mods/new")
        for (const name of ["Basics", "Modified Attributes", "Pattern Overrides", "Character Overrides", "Misc"]) {
            expect((await screen.findByRole("group", { name })).closest(".panel")).not.toBeNull()
        }
    })

    it("shows a validation error in an error banner", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
        renderForm("/supported-mods/new")
        await userEvent.click(await screen.findByRole("button", { name: /Save/i }))
        expect(screen.getByText("Name is required").closest(".banner-error")).not.toBeNull()
    })

    it("adds and removes a modified attribute chip", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ categories: [] }), { status: 200 }))
        renderForm("/supported-mods/new")
        await userEvent.type(await screen.findByRole("combobox", { name: "Add attribute" }), "melee_attack{Enter}")
        expect(screen.getByText("melee_attack").closest(".chip")).not.toBeNull()
        await userEvent.click(screen.getByRole("button", { name: "Remove melee_attack" }))
        expect(screen.queryByText("melee_attack")).not.toBeInTheDocument()
    })

    it("keeps the empty Basics state in its own module", () => {
        expect(emptyBasicsState).toEqual({ name: "", package_name: "", workshop_id: "", custom_path: false, path: "" })
    })
})
