import React from "react"
import ModCard, { NeedsSyncBadge, type ModCardProgressSegment } from "@/components/Dashboard/ModCard"
import { API_BASE } from "@/lib/config"
import { highlightMatch } from "@/lib/text"
import type { ModStatus } from "@/lib/types"

/** Props for {@link ModGrid}. */
interface ModGridProps {
    mods: ModStatus[]
    /** Receives the mod id. */
    onModSelect: (modId: string) => void
    /** Receives the mod id. */
    onModSync: (modId: string) => void
    searchQuery?: string
}

/**
 * Stateless grid rendering one {@link ModCard} per mod, laid out by the `.mod-grid` CSS class.
 *
 * @param mods Mods to display
 * @param onModSelect Called when a card is clicked
 * @param onModSync Called when a card's sync button is clicked
 * @param searchQuery Text to highlight
 * @returns The grid of mod cards.
 */
const ModGrid: React.FC<ModGridProps> = ({ mods, onModSelect, onModSync, searchQuery = "" }) => {
    return (
        <div className="mod-grid">
            {mods.map((mod) => {
                const segments: ModCardProgressSegment[] = []
                if (mod.user_translated > 0 && mod.total > 0) {
                    segments.push({
                        widthPercent: (mod.user_translated / mod.total) * 100,
                        background: "var(--accent-gradient)",
                        title: `${mod.user_translated} translated by you`,
                    })
                }
                if (mod.untouched > 0 && mod.total > 0) {
                    segments.push({
                        widthPercent: (mod.untouched / mod.total) * 100,
                        background: "rgba(148, 163, 184, 0.5)",
                        title: `${mod.untouched} untouched (pre-existing English)`,
                    })
                }
                return (
                    <ModCard
                        key={mod.id}
                        id={mod.id}
                        title={highlightMatch(mod.name, searchQuery)}
                        idBadge={mod.id}
                        subtitle={<>by {highlightMatch(mod.author || "Unknown", searchQuery)}</>}
                        previewImageUrl={mod.preview_image ? `${API_BASE}${mod.preview_image}` : null}
                        progress={{
                            leftLabel: `${mod.percentage}% Translated`,
                            rightLabel: `${mod.translated} / ${mod.total} strings`,
                            segments,
                        }}
                        stats={[
                            { value: mod.untranslated, label: "Remaining" },
                            { value: mod.has_dll ? "DLL" : "CSV", label: "Format" },
                        ]}
                        badges={mod.has_changes ? <NeedsSyncBadge /> : undefined}
                        primaryAction={{
                            label: "View",
                            variant: mod.untranslated > 0 ? "warning" : "primary",
                            onClick: () => onModSelect(mod.id),
                        }}
                        steamUrl={mod.url}
                        onSync={() => onModSync(mod.id)}
                    />
                )
            })}
        </div>
    )
}

export default ModGrid
