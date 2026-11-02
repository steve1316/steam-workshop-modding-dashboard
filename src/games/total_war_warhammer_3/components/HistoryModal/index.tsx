import React, { useCallback, useEffect, useState } from "react"

import type { HistoryEntry } from "@/shared_types"
import SharedHistoryModal from "@/translation/HistoryModal"
import { toHistoryModalEntry } from "@/translation/historyEntry"
import { createSnapshot, deleteSnapshot, listSnapshots, restoreSnapshot } from "@/games/total_war_warhammer_3/translationApi"
import { useConfirm } from "@/ui/useConfirm"

/** Props for `HistoryModal`. */
interface HistoryModalProps {
    workshopId: string
    onClose: () => void
    /** Renders the header as "Reset to snapshot" instead of "History". */
    defaultRestoreMode: boolean
    onRestored: () => void
}

/**
 * WH3 snapshot-history modal, a thin wrapper over the shared `HistoryModal`. Used by both the History toolbar button and the Reset action.
 *
 * @param workshopId Translation mod Workshop id.
 * @param onClose Called when the modal closes.
 * @param defaultRestoreMode Header reads "Reset to snapshot".
 * @param onRestored Called after a restore so the parent can re-fetch.
 * @returns The modal.
 */
const HistoryModal: React.FC<HistoryModalProps> = ({ workshopId, onClose, defaultRestoreMode, onRestored }) => {
    const [snaps, setSnaps] = useState<HistoryEntry[]>([])
    const [error, setError] = useState<string | null>(null)
    const { confirm, confirmDialog } = useConfirm()

    const refresh = useCallback(async () => {
        setError(null)
        try {
            setSnaps(await listSnapshots(workshopId))
        } catch (e) {
            setError((e as Error).message)
        }
    }, [workshopId])

    useEffect(() => {
        refresh()
    }, [refresh])

    const onSave = useCallback(
        async (label: string) => {
            await createSnapshot(workshopId, label || "manual save")
            await refresh()
        },
        [workshopId, refresh]
    )

    const onRestore = useCallback(
        async (entry: { id: string }) => {
            const ok = await confirm({
                title: "Restore snapshot",
                message: "Restore from this snapshot? Your current state will be auto-snapshotted first.",
                confirmLabel: "Restore",
                variant: "warning",
            })
            if (!ok) return
            try {
                await restoreSnapshot(workshopId, entry.id)
                onRestored()
                await refresh()
            } catch (e) {
                setError((e as Error).message)
            }
        },
        [workshopId, refresh, onRestored, confirm]
    )

    const onDelete = useCallback(
        async (entry: { id: string }) => {
            const ok = await confirm({ title: "Delete snapshot", message: "Delete this snapshot? This cannot be undone.", confirmLabel: "Delete snapshot", variant: "danger" })
            if (!ok) return
            try {
                await deleteSnapshot(workshopId, entry.id)
                await refresh()
            } catch (e) {
                setError((e as Error).message)
            }
        },
        [workshopId, refresh, confirm]
    )

    return (
        <>
            <SharedHistoryModal
                title={defaultRestoreMode ? "Reset to snapshot" : "History"}
                entries={snaps.map(toHistoryModalEntry)}
                onSave={onSave}
                onRestore={onRestore}
                onDelete={onDelete}
                onClose={onClose}
                emptyMessage="No snapshots yet."
                error={error}
            />
            {confirmDialog}
        </>
    )
}

export default HistoryModal
