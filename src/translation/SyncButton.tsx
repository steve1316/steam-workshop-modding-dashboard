import { useState } from "react"
import { FaFileExport } from "react-icons/fa"

import { useConfirm } from "@/ui/useConfirm"

/** Which of the three sync states the button shows. */
export type SyncState = "sync" | "resync" | "disabled"

/** Props for SyncButton. */
interface SyncButtonProps {
    /** "sync" while there are unsynced changes, "resync" when a previous sync can be repeated, "disabled" otherwise. */
    state: SyncState
    /** Confirm dialog body for a sync (`resync` false) or a re-sync (`resync` true). */
    confirmMessage: (resync: boolean) => string
    /** Runs the sync after confirming. The button reads "Syncing..." until it settles. */
    onSync: (resync: boolean) => Promise<void>
}

/**
 * Sync button that confirms first, runs `onSync`, and blocks repeat clicks while syncing.
 *
 * @param state - Label and enabled state to show.
 * @param confirmMessage - Builds the confirm dialog body.
 * @param onSync - Runs the sync.
 * @returns The button and its confirm dialog.
 */
export function SyncButton({ state, confirmMessage, onSync }: SyncButtonProps) {
    const { confirm, confirmDialog } = useConfirm()
    const [busy, setBusy] = useState(false)
    const resync = state === "resync"
    const label = resync ? "Re-sync Changes" : "Sync Changes"

    const handleClick = async () => {
        const ok = await confirm({ title: label, message: confirmMessage(resync), confirmLabel: resync ? "Re-sync" : "Sync", variant: "warning" })
        if (!ok) return
        setBusy(true)
        try {
            await onSync(resync)
        } finally {
            setBusy(false)
        }
    }

    return (
        <>
            <button type="button" className="btn btn-primary" onClick={handleClick} disabled={state === "disabled" || busy}>
                <FaFileExport />
                {busy ? "Syncing..." : label}
            </button>
            {confirmDialog}
        </>
    )
}
