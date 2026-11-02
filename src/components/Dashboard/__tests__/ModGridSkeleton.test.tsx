import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import ModGridSkeleton from "@/components/Dashboard/ModGridSkeleton"

describe("ModGridSkeleton", () => {
    it("announces a busy loading status", () => {
        render(<ModGridSkeleton />)
        const status = screen.getByRole("status", { name: /loading mods/i })
        expect(status).toHaveAttribute("aria-busy", "true")
    })

    it("renders the requested number of placeholder cards inside the mod grid", () => {
        const { container } = render(<ModGridSkeleton count={4} />)
        expect(container.querySelector(".mod-grid")).not.toBeNull()
        expect(container.querySelectorAll(".mod-card-skeleton")).toHaveLength(4)
    })

    it("uses a custom label when given one", () => {
        render(<ModGridSkeleton label="Loading translation mods" />)
        expect(screen.getByRole("status", { name: /loading translation mods/i })).toBeInTheDocument()
    })
})
