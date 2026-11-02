import type { ReactNode } from "react"

import ModGridSkeleton from "@/components/ModGridSkeleton"

/** Props for DashboardSection. */
interface DashboardSectionProps {
    /** e.g. "Pack Mods". Omit for a single untitled grid. */
    title?: string
    /** Shows skeleton cards. */
    loading: boolean
    /** Defaults to the skeleton's own default (6). */
    skeletonCount?: number
    /** Defaults to "Loading mods". */
    skeletonLabel?: string
    /** Shown in place of the grid. Set only when there are no cards. */
    error?: string | null
    /** When given with `error`, a Retry button calls it. */
    onRetry?: () => void
    empty: boolean
    /** Line shown when `empty`, e.g. "No mods found." or a no-match message for the current search. */
    emptyMessage: string
    children: ReactNode
}

/**
 * One titled block of a dashboard. It shows exactly one of: the load error with Retry, skeleton cards, an empty line, or the card grid.
 *
 * @param title Section heading.
 * @param loading Whether the list is loading.
 * @param skeletonCount Skeleton card count.
 * @param skeletonLabel Skeleton accessible label.
 * @param error Load error.
 * @param onRetry Retry handler.
 * @param empty Whether there is nothing to list.
 * @param emptyMessage Line shown when empty.
 * @param children The card grid.
 * @returns The section.
 */
export default function DashboardSection({ title, loading, skeletonCount, skeletonLabel, error, onRetry, empty, emptyMessage, children }: DashboardSectionProps) {
    let body: ReactNode
    if (error) {
        body = (
            <div className="dashboard-section-error" role="alert">
                <span>{error}</span>
                {onRetry && (
                    <button type="button" className="btn btn-outline btn-sm" onClick={onRetry}>
                        Retry
                    </button>
                )}
            </div>
        )
    } else if (loading) {
        body = <ModGridSkeleton count={skeletonCount} label={skeletonLabel} />
    } else if (empty) {
        body = <p className="dashboard-section-empty">{emptyMessage}</p>
    } else {
        body = children
    }

    return (
        <section className="dashboard-section">
            {title && <h2 className="dashboard-section-title">{title}</h2>}
            {body}
        </section>
    )
}
