import WorkshopCard from "@/components/WorkshopCard"
import { API_BASE } from "@/config"
import type { SupportedMod, ValidationIssue } from "@/games/total_war_warhammer_3/api"
import ValidationBadge from "@/games/total_war_warhammer_3/components/ValidationBadge"

/** Props for `SupportedModCard`. */
interface Props {
    mod: SupportedMod
    issues: ValidationIssue[]
    /** The Edit button is omitted when not provided. */
    onEdit?: (packageName: string) => void
}

/**
 * Card for one TW3 supported-mod entry, wrapping `WorkshopCard` with the validation issues, modified attributes, Edit, and "Open Workshop Folder" controls.
 *
 * @param mod Registry entry.
 * @param issues Issues affecting this mod, empty to hide the badge.
 * @param onEdit Called with the mod's `package_name` on Edit.
 * @returns The card.
 */
const SupportedModCard = ({ mod, issues, onEdit }: Props) => {
    const previewImageUrl = mod.workshop_id ? `${API_BASE}/games/total_war_warhammer_3/packs/${mod.workshop_id}/preview` : null
    const hasAttributes = !!mod.modified_attributes && mod.modified_attributes.length > 0
    return (
        <WorkshopCard previewImageUrl={previewImageUrl} previewAlt={mod.name} title={mod.name} idBadge={mod.workshop_id ?? undefined} subtitle={mod.package_name}>
            {issues.length > 0 && (
                <details>
                    <summary style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                        <ValidationBadge issues={issues} />
                        <span style={{ fontSize: "0.85em", color: "var(--warning)" }}>
                            {issues.length} validation issue{issues.length === 1 ? "" : "s"}
                        </span>
                    </summary>
                    <ul style={{ margin: "0.5rem 0 0 1.25rem", padding: 0, fontSize: "0.8em", color: "var(--text-dim)", wordBreak: "break-word" }}>
                        {issues.map((issue, i) => (
                            <li key={i}>{issue.message}</li>
                        ))}
                    </ul>
                </details>
            )}
            {/* Pinned to the bottom so the attributes line sits at the same height on every card. */}
            {(hasAttributes || onEdit || mod.workshop_id) && (
                <div data-testid="supported-mod-card-footer" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "auto" }}>
                    {hasAttributes && (
                        <p style={{ margin: 0, fontSize: "0.9em" }}>
                            <strong>Modified attributes:</strong> {mod.modified_attributes!.join(", ")}
                        </p>
                    )}
                    {(onEdit || mod.workshop_id) && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                            {onEdit && (
                                <button type="button" className="btn btn-outline btn-compact" onClick={() => onEdit(mod.package_name)}>
                                    Edit
                                </button>
                            )}
                            {mod.workshop_id && (
                                <button
                                    type="button"
                                    className="btn btn-outline btn-compact"
                                    onClick={async () => {
                                        try {
                                            await fetch(`${API_BASE}/games/total_war_warhammer_3/packs/${mod.workshop_id}/open`, { method: "POST" })
                                        } catch (err) {
                                            console.error("Failed to open workshop folder:", err)
                                        }
                                    }}
                                >
                                    Open Workshop Folder
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </WorkshopCard>
    )
}

export default SupportedModCard
