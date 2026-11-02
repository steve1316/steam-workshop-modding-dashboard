import { useCallback, useEffect, useState } from "react"
import { gameApi } from "@/lib/api"
import type { HistoryEntry } from "@/lib/types"
import SharedHistoryModal from "@/components/HistoryModal"
import { toHistoryModalEntry } from "@/components/HistoryModal/helpers"

/** Props for BackupHistoryModal. */
interface BackupHistoryModalProps {
    modId: string
    onClose: () => void
    /** Restore requested. The parent opens the confirm dialog. */
    onRestore: (entry: HistoryEntry) => void
    /** Delete requested. The parent opens the confirm dialog. */
    onDelete: (entry: HistoryEntry) => void
    /** Bump to re-fetch the list (e.g. after a confirmed delete). */
    refreshKey?: number
}

/**
 * Backup-history modal, a thin wrapper over the shared `HistoryModal` that owns the history API calls.
 * @param modId - Mod's Workshop id.
 * @param onClose - Close handler.
 * @param onRestore - Restore handler.
 * @param onDelete - Delete handler.
 * @param refreshKey - Bump to re-fetch.
 * @returns The modal.
 */
export default function BackupHistoryModal({ modId, onClose, onRestore, onDelete, refreshKey }: BackupHistoryModalProps) {
    const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([])

    const fetchHistory = useCallback(async () => {
        try {
            const res = await gameApi("chrono_ark").get(`/mods/${modId}/history`)
            if (res.ok) setHistoryEntries(await res.json())
        } catch (err) {
            console.error("Failed to fetch history:", err)
        }
    }, [modId])

    useEffect(() => {
        fetchHistory()
    }, [fetchHistory, refreshKey])

    const onSave = useCallback(
        async (label: string) => {
            await gameApi("chrono_ark").post(`/mods/${modId}/history`, { label })
            await fetchHistory()
        },
        [modId, fetchHistory]
    )

    const byId = new Map(historyEntries.map((e) => [e.id, e]))

    return (
        <SharedHistoryModal
            entries={historyEntries.map(toHistoryModalEntry)}
            onSave={onSave}
            onRestore={(entry) => {
                const orig = byId.get(entry.id)
                if (orig) onRestore(orig)
            }}
            onDelete={(entry) => {
                const orig = byId.get(entry.id)
                if (orig) onDelete(orig)
            }}
            onClose={onClose}
            emptyMessage="No backups available yet. Backups are created automatically before destructive operations."
        />
    )
}
