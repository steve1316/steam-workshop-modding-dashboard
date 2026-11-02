import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { FaSteam, FaFolderOpen } from "react-icons/fa"
import WorkshopCard from "@/components/Dashboard/WorkshopCard"
import { API_BASE, fetchJson } from "@/lib/api"
import HighlightText from "@/components/ui/HighlightText"
import PublishWorkshopDialog from "@/games/total_war_warhammer_3/components/PublishWorkshopDialog"
import ScriptRunButton from "@/games/total_war_warhammer_3/components/ScriptRunButton"

/**
 * Format a unix timestamp as a relative "<label> ... ago" string. Sub-hour deltas read `"<1h ago"`, under a day is whole hours, and beyond that is days with one decimal.
 *
 * @param label Prefix such as `"Rebuilt"`.
 * @param unix Event time in seconds.
 * @param nowMs Current time in ms, injectable for tests.
 * @returns A label such as `"Rebuilt 3h ago"`.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function formatAgo(label: string, unix: number, nowMs: number = Date.now()): string {
    const deltaSeconds = Math.max(0, nowMs / 1000 - unix)
    const hours = Math.floor(deltaSeconds / 3600)
    if (hours < 1) return `${label} <1h ago`
    if (hours < 24) return `${label} ${hours}h ago`
    const days = parseFloat((deltaSeconds / 86400).toFixed(1))
    return `${label} ${days} days ago`
}

/** A single compat pack card shown on the TW3 Dashboard. */
export interface PackEntry {
    title: string
    workshopId: string
    /** Omit for mods that have no rebuild pipeline. */
    scriptId?: string
    /** Shown when multiple packs share a script. */
    sharedNote?: string
}

/** Props for `PackCardComponent`. */
interface PackCardProps {
    pack: PackEntry
    /** Trimmed dashboard search text, highlighted in the title. */
    searchQuery?: string
}

/**
 * TW3 dashboard card wrapping `WorkshopCard` with a title, workshopId badge, optional note, Rebuild button, and Steam link.
 *
 * @param pack Pack metadata.
 * @param searchQuery Search text to highlight in the title.
 * @returns The pack card.
 */
const PackCardComponent = ({ pack, searchQuery = "" }: PackCardProps) => {
    const [publishOpen, setPublishOpen] = useState(false)
    const previewImageUrl = `${API_BASE}/games/total_war_warhammer_3/packs/${pack.workshopId}/preview`
    const workshopUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${pack.workshopId}`

    // A failed lookup just leaves the subtitle off.
    const { data: times } = useQuery({
        queryKey: ["total_war_warhammer_3", "pack-times", pack.workshopId],
        queryFn: () => fetchJson<{ last_modified_unix?: number | null; published_unix?: number | null }>(`${API_BASE}/games/total_war_warhammer_3/packs/${pack.workshopId}/last_modified`),
    })
    const lastModifiedUnix = typeof times?.last_modified_unix === "number" ? times.last_modified_unix : null
    const publishedUnix = typeof times?.published_unix === "number" ? times.published_unix : null

    const subtitle =
        lastModifiedUnix !== null || publishedUnix !== null ? (
            <>
                {lastModifiedUnix !== null && <span title="Last time the local pack files changed on disk">{formatAgo("Rebuilt", lastModifiedUnix)}</span>}
                {lastModifiedUnix !== null && publishedUnix !== null && <br />}
                {publishedUnix !== null && <span title="Last time this item was updated on the Steam Workshop">{formatAgo("Published", publishedUnix)}</span>}
            </>
        ) : undefined

    return (
        <>
            <WorkshopCard previewImageUrl={previewImageUrl} previewAlt={pack.title} title={<HighlightText text={pack.title} query={searchQuery} />} idBadge={pack.workshopId} subtitle={subtitle}>
                <div className="mod-card-footer">
                    {pack.sharedNote && <p style={{ fontSize: "0.85em", color: "var(--text-dim)", margin: 0 }}>{pack.sharedNote}</p>}
                    <div className="mod-actions" style={{ flexWrap: "nowrap", gap: "0.5rem" }}>
                        {pack.scriptId ? (
                            <ScriptRunButton scriptId={pack.scriptId} label="Rebuild" className="btn-compact" />
                        ) : (
                            <button type="button" className="btn btn-primary btn-compact" disabled title="No rebuild script associated with this mod">
                                Rebuild
                            </button>
                        )}
                        <button className="btn btn-outline btn-compact" onClick={() => setPublishOpen(true)} title="Push the local pack to the Steam Workshop">
                            Publish
                        </button>
                        <button
                            type="button"
                            className="btn btn-outline btn-icon"
                            onClick={() => {
                                fetch(`${API_BASE}/games/total_war_warhammer_3/packs/${pack.workshopId}/open`, { method: "POST" }).catch(() => {})
                            }}
                            aria-label="Open local pack folder"
                            title="Open local pack folder"
                        >
                            <FaFolderOpen size={18} />
                        </button>
                        <a href={workshopUrl} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-icon" aria-label="Open Steam workshop page" title="Open Steam workshop page">
                            <FaSteam size={20} />
                        </a>
                    </div>
                </div>
            </WorkshopCard>
            {publishOpen && <PublishWorkshopDialog workshopId={pack.workshopId} title={pack.title} onClose={() => setPublishOpen(false)} />}
        </>
    )
}

export default PackCardComponent
