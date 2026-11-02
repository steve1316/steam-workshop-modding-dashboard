import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it } from "vitest"

import SearchInput from "@/ui/SearchInput"

/**
 * Controlled harness around SearchInput.
 *
 * @returns The harness element.
 */
function Harness() {
    const [value, setValue] = useState("")
    return <SearchInput value={value} onChange={setValue} placeholder="Search keys or text..." />
}

describe("SearchInput", () => {
    it("types into the field and clears with the Clear search button", async () => {
        render(<Harness />)
        const input = screen.getByPlaceholderText("Search keys or text...")
        expect(screen.queryByRole("button", { name: "Clear search" })).not.toBeInTheDocument()
        await userEvent.type(input, "roland")
        expect(input).toHaveValue("roland")
        await userEvent.click(screen.getByRole("button", { name: "Clear search" }))
        expect(input).toHaveValue("")
    })
})
