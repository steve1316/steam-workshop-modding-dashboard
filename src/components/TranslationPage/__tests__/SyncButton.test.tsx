import { render, screen, waitFor, within } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { SyncButton } from "@/components/TranslationPage/SyncButton"

const message = (resync: boolean) => (resync ? "Re-sync everything?" : "Overwrite the files?")

describe("SyncButton", () => {
    it("labels each state and disables the idle state", () => {
        const { rerender } = render(<SyncButton state="sync" confirmMessage={message} onSync={vi.fn()} />)
        expect(screen.getByRole("button", { name: "Sync Changes" })).toBeEnabled()
        rerender(<SyncButton state="resync" confirmMessage={message} onSync={vi.fn()} />)
        expect(screen.getByRole("button", { name: "Re-sync Changes" })).toBeEnabled()
        rerender(<SyncButton state="disabled" confirmMessage={message} onSync={vi.fn()} />)
        expect(screen.getByRole("button", { name: "Sync Changes" })).toBeDisabled()
    })

    it("asks for confirmation, then syncs and shows Syncing... until it settles", async () => {
        let finish: () => void = () => {}
        const onSync = vi.fn(() => new Promise<void>((r) => (finish = r)))
        render(<SyncButton state="resync" confirmMessage={message} onSync={onSync} />)
        await userEvent.click(screen.getByRole("button", { name: "Re-sync Changes" }))
        const dialog = screen.getByRole("dialog", { name: "Re-sync Changes" })
        expect(dialog).toHaveTextContent("Re-sync everything?")
        await userEvent.click(within(dialog).getByRole("button", { name: "Re-sync" }))
        expect(onSync).toHaveBeenCalledWith(true)
        const busy = screen.getByRole("button", { name: "Syncing..." })
        expect(busy).toBeDisabled()
        await userEvent.click(busy)
        expect(onSync).toHaveBeenCalledTimes(1)
        finish()
        await waitFor(() => expect(screen.getByRole("button", { name: "Re-sync Changes" })).toBeEnabled())
    })

    it("does nothing when the user cancels", async () => {
        const onSync = vi.fn()
        render(<SyncButton state="sync" confirmMessage={message} onSync={onSync} />)
        await userEvent.click(screen.getByRole("button", { name: "Sync Changes" }))
        await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }))
        expect(onSync).not.toHaveBeenCalled()
    })
})
