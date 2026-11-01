import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"
import { gameApi } from "../../../../api/games"
import SharedHistoryModal from "../../../../translation/HistoryModal"

/** One backup history entry for a mod. */
export interface HistoryEntry {
    id: string
    /** Why the backup was created (e.g. "Before translation run"). */
    reason: string
    /** "auto" for backups taken before destructive ops, "manual" for user saves. */
    kind?: "auto" | "manual"
    /** ISO timestamp. */
    created_at: string
    files: string[]
    /** Translated string count at backup time, when recorded. */
    translated_count?: number
    /** Total translatable string count at backup time, when recorded. */
    total_count?: number
    /** Glossary term count at backup time, when recorded. */
    glossary_count?: number
}

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
 * Build the counts subtitle (translated/total strings and glossary terms).
 * @param entry - Backup entry.
 * @returns The subtitle, or `undefined` when no counts were recorded.
 */
function renderCounts(entry: HistoryEntry): ReactNode {
    const hasCounts = (entry.total_count ?? 0) > 0
    const hasGlossary = (entry.glossary_count ?? 0) > 0
    if (!hasCounts && !hasGlossary) return undefined
    return (
        <>
            {hasCounts && (
                <span>
                    {entry.translated_count} / {entry.total_count} strings translated
                </span>
            )}
            {hasCounts && hasGlossary && <span> &middot; </span>}
            {hasGlossary && (
                <span>
                    {entry.glossary_count} glossary term{entry.glossary_count !== 1 ? "s" : ""}
                </span>
            )}
        </>
    )
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
            entries={historyEntries.map((e) => ({ id: e.id, title: e.reason, kind: e.kind ?? "auto", createdAt: e.created_at, subtitle: renderCounts(e) }))}
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
