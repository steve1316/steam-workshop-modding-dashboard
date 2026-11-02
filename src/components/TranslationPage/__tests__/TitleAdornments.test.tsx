import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { OpenFolderButton, PendingSyncPill, SteamLink } from "@/components/TranslationPage/TitleAdornments"

describe("title adornments", () => {
    it("links to the Steam Workshop page in a new tab", () => {
        render(<SteamLink href="https://steamcommunity.com/sharedfiles/filedetails/?id=1" />)
        const link = screen.getByRole("link", { name: "Open on Steam Workshop" })
        expect(link).toHaveAttribute("href", "https://steamcommunity.com/sharedfiles/filedetails/?id=1")
        expect(link).toHaveAttribute("target", "_blank")
        expect(link).toHaveClass("icon-action", "icon-action-steam")
    })

    it("opens the local folder when the folder button is clicked", async () => {
        const onClick = vi.fn()
        render(<OpenFolderButton onClick={onClick} />)
        await userEvent.click(screen.getByRole("button", { name: "Open local folder" }))
        expect(onClick).toHaveBeenCalledTimes(1)
    })

    it("renders the pending sync pill with the warning tone", () => {
        render(<PendingSyncPill />)
        expect(screen.getByText("Changes pending sync")).toHaveClass("pill", "pill-warning")
    })
})
