import type { ReactNode } from "react"
import type { HistoryEntry } from "../shared_types"
import type { HistoryModalEntry } from "./HistoryModal"

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
 * Map a backend history entry onto the modal's row shape.
 * @param entry - Backup entry from a `history` or `snapshots` list.
 * @returns The row.
 */
export function toHistoryModalEntry(entry: HistoryEntry): HistoryModalEntry {
    return { id: entry.id, title: entry.reason, kind: entry.kind ?? "auto", createdAt: entry.created_at, subtitle: renderCounts(entry) }
}
