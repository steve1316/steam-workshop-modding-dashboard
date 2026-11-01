import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useGameSlug } from "../../../useGameSlug"

import ModCard, { NeedsSyncBadge, type ModCardProgressSegment, type ModCardStat } from "../../../../components/ModCard"
import { API_BASE } from "../../../../config"
import { rememberScrollTarget } from "../../../../dashboard/useScrollRestore"
import { highlightMatch } from "../../../../utils/text"
import type { WH3RescanSummary, WH3TranslationModSummary } from "../../../../shared_types"
import { syncChanges } from "../../translationApi"
import PublishWorkshopDialog, { type PublishPrepareStep } from "../PublishWorkshopDialog"

/** Props for TranslationModCard. */
export interface TranslationModCardProps {
    mod: WH3TranslationModSummary
    /** Null when the mod has not been scanned this session. */
    progress: WH3RescanSummary | null
    /** Receives the mod's workshop id. */
    onRescan: (workshopId: string) => void
    /** Trimmed dashboard search text, highlighted in the title. */
    searchQuery?: string
}

/**
 * Dashboard card for one WH3 translation mod, built on the shared `ModCard` shell so it matches Chrono Ark's card. The Publish button syncs first when needed.
 *
 * @param mod Registry summary.
 * @param progress Latest rescan result, or null if not yet scanned.
 * @param onRescan Called on the rescan icon.
 * @param searchQuery Search text to highlight in the title.
 * @returns The card.
 */
const TranslationModCard: React.FC<TranslationModCardProps> = ({ mod, progress, onRescan, searchQuery = "" }) => {
    const navigate = useNavigate()
    const slug = useGameSlug()
    // Whether the open publish dialog syncs first, fixed when it opens so the post-sync rescan does not drop the step. Null while closed.
    const [publishSyncFirst, setPublishSyncFirst] = useState<boolean | null>(null)
    const parents = mod.parent_workshop_ids
    // Use the strings table's statuses so the card never shows a count the table has no filter for.
    const counts = progress?.canonical_counts ?? null
    const translated = counts ? counts.synced + counts.pending : 0
    const untouched = counts?.untouched ?? 0
    const untranslated = (counts?.missing ?? 0) + (counts?.changed ?? 0)
    const done = translated + untouched
    const total = done + untranslated
    const percent = total > 0 ? Math.round((done / total) * 100) : 0

    const singleParent = parents.length === 1 ? parents[0] : null
    const parentSteamUrl = singleParent ? `https://steamcommunity.com/sharedfiles/filedetails/?id=${singleParent}` : null
    const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${mod.workshop_id}`

    const segments: ModCardProgressSegment[] = []
    if (counts && total > 0) {
        if (translated > 0) {
            segments.push({
                widthPercent: (translated / total) * 100,
                background: "var(--accent-gradient)",
                title: `${translated} translated by you`,
            })
        }
        if (untouched > 0) {
            segments.push({
                widthPercent: (untouched / total) * 100,
                background: "rgba(148, 163, 184, 0.5)",
                title: `${untouched} untouched (pre-existing English)`,
            })
        }
    }

    const stats: ModCardStat[] = [
        { value: untranslated, label: "Remaining" },
        { value: "LOC", label: "Format" },
    ]

    const needsSync = progress?.has_unsynced_changes ?? false
    // Sync writes the translations into the loose files and rebuilds the .pack, so the publish pushes the latest strings.
    const syncStep: PublishPrepareStep | undefined = publishSyncFirst
        ? {
              note: "This mod has unsynced translation changes. They will be synced and the pack rebuilt before publishing.",
              status: "Syncing translations and rebuilding the pack...",
              run: async () => {
                  const result = await syncChanges(mod.workshop_id)
                  onRescan(mod.workshop_id)
                  if (result.pack_error) throw new Error(`Translations were synced, but the pack rebuild failed so the publish was stopped: ${result.pack_error}`)
              },
          }
        : undefined

    return (
        <>
            <ModCard
                id={mod.workshop_id}
                title={highlightMatch(mod.display_name, searchQuery)}
                idBadge={mod.workshop_id}
                subtitle={
                    singleParent ? (
                        <a href={parentSteamUrl ?? "#"} target="_blank" rel="noopener noreferrer" className="translation-parent-link" aria-label={`parent mod ${singleParent}`}>
                            Parent mod
                        </a>
                    ) : parents.length > 1 ? (
                        <span className="translation-parent-link" title={parents.join(", ")}>
                            Translates {parents.length} mods
                        </span>
                    ) : undefined
                }
                previewImageUrl={mod.preview_image_url ? `${API_BASE}${mod.preview_image_url}` : null}
                progress={{
                    leftLabel: counts ? `${percent}% Translated` : "Not yet scanned",
                    rightLabel: counts ? `${done} / ${total} strings` : undefined,
                    segments,
                }}
                stats={stats}
                badges={progress?.has_unsynced_changes ? <NeedsSyncBadge /> : undefined}
                primaryAction={{
                    label: "View",
                    variant: untranslated > 0 ? "warning" : "primary",
                    onClick: () => {
                        rememberScrollTarget(mod.workshop_id)
                        navigate(`/${slug}/translation/${mod.workshop_id}`)
                    },
                }}
                secondaryAction={{
                    label: "Publish",
                    onClick: () => setPublishSyncFirst(needsSync),
                    title: needsSync ? "Sync the translations, rebuild the pack, then push it to the Steam Workshop" : "Push the local pack to the Steam Workshop",
                }}
                steamUrl={steamUrl}
                onSync={() => onRescan(mod.workshop_id)}
            />
            {publishSyncFirst !== null && <PublishWorkshopDialog workshopId={mod.workshop_id} title={mod.display_name} prepare={syncStep} onClose={() => setPublishSyncFirst(null)} />}
        </>
    )
}

export default TranslationModCard
