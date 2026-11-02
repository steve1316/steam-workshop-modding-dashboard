import React, { type ReactNode } from "react"
import { Link } from "react-router-dom"
import { FaExclamationCircle, FaSteam, FaSync } from "react-icons/fa"
import WorkshopCard from "@/components/WorkshopCard"

/** One stat box rendered in the `mod-stats` row. */
export interface ModCardStat {
    value: ReactNode
    label: ReactNode
}

/** One segment of the stacked progress bar. */
export interface ModCardProgressSegment {
    /** Percentage of the bar, 0-100. */
    widthPercent: number
    background: string
    title?: string
}

/** Progress section configuration. */
export interface ModCardProgress {
    /** e.g. `"75% Translated"`. */
    leftLabel: ReactNode
    /** e.g. `"15 / 20 strings"`. Omit to render only the left label. */
    rightLabel?: ReactNode
    /** Rendered left-to-right. */
    segments: ModCardProgressSegment[]
}

/** Primary action button or link. Either `to` (Link) or `onClick` (button) must be set, not both. */
export type ModCardPrimaryAction = {
    label: ReactNode
    /** Defaults to `"primary"`. */
    variant?: "primary" | "warning"
} & ({ to: string; onClick?: never } | { onClick: () => void; to?: never })

/** Optional second button rendered next to the primary action with outline styling. */
export interface ModCardSecondaryAction {
    /** Button text. */
    label: ReactNode
    onClick: () => void
    title?: string
}

/** Props for ModCard. */
interface ModCardProps {
    /** Used for the `data-mod-id` attribute. */
    id: string
    title: ReactNode
    /** Shown right of the title, e.g. workshop id. */
    idBadge: string
    /** Beneath the title, e.g. author or language pair. */
    subtitle?: ReactNode
    /** Null or missing renders a placeholder. */
    previewImageUrl?: string | null
    progress: ModCardProgress
    stats: ModCardStat[]
    /** Appended after the stat boxes, e.g. `NeedsSyncBadge`. */
    badges?: ReactNode
    /** Rendered as a `<Link>` when `to` is set, otherwise a `<button>`. */
    primaryAction: ModCardPrimaryAction
    /** Rendered next to the primary action, e.g. `Publish`. */
    secondaryAction?: ModCardSecondaryAction
    /** Rendered as a Steam icon link. */
    steamUrl?: string | null
    /** When undefined, the sync icon button is hidden. */
    onSync?: () => void
}

/**
 * Dashboard card for a single mod, shared by Chrono Ark (`ModGrid`) and WH3 (`TranslationModCard`). Memoized so sibling updates do not re-render it.
 *
 * @param props See `ModCardProps`.
 * @returns The mod card.
 */
const ModCard: React.FC<ModCardProps> = React.memo((props) => {
    const { id, title, idBadge, subtitle, previewImageUrl, progress, stats, badges, primaryAction, secondaryAction, steamUrl, onSync } = props
    const variantClass = primaryAction.variant === "warning" ? "btn-warning" : "btn-primary"
    return (
        <WorkshopCard data-mod-id={id} previewImageUrl={previewImageUrl ?? null} previewAlt={typeof title === "string" ? title : "Mod"} title={title} idBadge={idBadge} subtitle={subtitle}>
            {/* Pinned to the bottom so progress, stats, and actions line up across cards with different title lengths. */}
            <div className="mod-card-footer">
                <div className="progress-section">
                    <div className="progress-info">
                        <span>{progress.leftLabel}</span>
                        {progress.rightLabel != null && <span>{progress.rightLabel}</span>}
                    </div>
                    <div className="progress-bar-bg" style={{ display: "flex" }}>
                        {progress.segments.map((seg, i) => (
                            <div
                                key={i}
                                title={seg.title}
                                style={{
                                    height: "100%",
                                    width: `${seg.widthPercent}%`,
                                    background: seg.background,
                                    transition: "width 1s ease-out",
                                }}
                            />
                        ))}
                    </div>
                </div>
                <div className="mod-stats">
                    {stats.map((stat, i) => (
                        <div key={i} className="stat-item">
                            <span className="stat-value">{stat.value}</span>
                            <span className="stat-label">{stat.label}</span>
                        </div>
                    ))}
                    {badges}
                </div>
                <div className="mod-actions">
                    {primaryAction.to != null ? (
                        <Link
                            to={primaryAction.to}
                            className={`btn ${variantClass}`}
                            style={{ flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", textDecoration: "none" }}
                        >
                            {primaryAction.label}
                        </Link>
                    ) : (
                        <button className={`btn ${variantClass}`} style={{ flex: 1 }} onClick={primaryAction.onClick}>
                            {primaryAction.label}
                        </button>
                    )}
                    {secondaryAction && (
                        <button className="btn btn-outline" style={{ flex: 1 }} onClick={secondaryAction.onClick} title={secondaryAction.title}>
                            {secondaryAction.label}
                        </button>
                    )}
                    {steamUrl && (
                        <a href={steamUrl} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-icon" title="Open mod page">
                            <FaSteam size={20} />
                        </a>
                    )}
                    {onSync && (
                        <button className="btn btn-outline btn-icon" onClick={onSync} title="Rescan workshop folder">
                            <FaSync />
                        </button>
                    )}
                </div>
            </div>
        </WorkshopCard>
    )
})

/**
 * "Needs Sync" badge for Chrono Ark mods with unsynced changes, exported for use in `badges`.
 *
 * @returns The badge.
 */
export const NeedsSyncBadge: React.FC = () => (
    <span
        style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.3rem",
            fontSize: "0.7rem",
            padding: "0.25rem 0.5rem",
            background: "rgba(251, 191, 36, 0.15)",
            border: "1px solid rgba(251, 191, 36, 0.3)",
            borderRadius: "6px",
            color: "#fbbf24",
            fontWeight: 600,
        }}
        title="Has unsynced changes"
    >
        <FaExclamationCircle size={10} />
        Needs Sync
    </span>
)

export default ModCard
