import { useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { fetchJson, gameApi } from "@/lib/api"
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
    // A failed load shows the empty list rather than an error.
    const { data: historyEntries = [], refetch } = useQuery({
        queryKey: ["chrono_ark", "history", modId, refreshKey],
        queryFn: () => fetchJson<HistoryEntry[]>(gameApi("chrono_ark").url(`/mods/${modId}/history`)),
    })

    const onSave = useCallback(
        async (label: string) => {
            await gameApi("chrono_ark").post(`/mods/${modId}/history`, { label })
            await refetch()
        },
        [modId, refetch]
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
