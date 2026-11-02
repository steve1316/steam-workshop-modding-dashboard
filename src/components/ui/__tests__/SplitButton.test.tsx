import { fireEvent, render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import SplitButton from "@/components/ui/SplitButton"

/**
 * Render a split button with one menu item.
 *
 * @param onSelect Handler for the menu item.
 */
function renderButton(onSelect = vi.fn()) {
    render(
        <div>
            <SplitButton label="Translate (Claude)" onClick={vi.fn()} menuLabel="Translate options" items={[{ label: "Re-Translate All", onSelect }]} />
            <p>outside</p>
        </div>
    )
}

describe("SplitButton", () => {
    it("opens its menu from the chevron and runs the chosen item", async () => {
        const onSelect = vi.fn()
        renderButton(onSelect)
        expect(screen.queryByRole("menu")).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Translate options" }))
        await userEvent.click(screen.getByRole("menuitem", { name: "Re-Translate All" }))
        expect(onSelect).toHaveBeenCalledTimes(1)
        expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    })

    it("closes the menu on Escape and on a click outside", async () => {
        renderButton()
        await userEvent.click(screen.getByRole("button", { name: "Translate options" }))
        await userEvent.keyboard("{Escape}")
        expect(screen.queryByRole("menu")).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Translate options" }))
        fireEvent.mouseDown(screen.getByText("outside"))
        expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    })

    it("disables both halves when disabled", () => {
        render(<SplitButton label="Translate" onClick={vi.fn()} items={[]} disabled />)
        expect(screen.getByRole("button", { name: "Translate" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "More options" })).toBeDisabled()
    })

    it("uses the outline style on both halves and the menu when variant is outline", async () => {
        render(<SplitButton label="Translate Names" onClick={vi.fn()} items={[{ label: "Suggest", onSelect: vi.fn() }]} variant="outline" />)
        expect(screen.getByRole("button", { name: "Translate Names" })).toHaveClass("btn-outline")
        expect(screen.getByRole("button", { name: "More options" })).toHaveClass("btn-outline")
        await userEvent.click(screen.getByRole("button", { name: "More options" }))
        expect(screen.getByRole("menuitem", { name: "Suggest" })).toHaveClass("btn-outline")
        expect(screen.getByRole("button", { name: "Translate Names" })).not.toHaveClass("btn-primary")
    })
})
