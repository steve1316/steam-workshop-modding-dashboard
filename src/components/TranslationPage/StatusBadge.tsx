import type { RowStatus } from "@/lib/types"
import { statusToChip } from "@/components/TranslationPage/helpers"

/** Props for StatusBadge. */
interface StatusBadgeProps {
    status: RowStatus
    /** Tooltip, shown only for the "untranslatable" status. */
    reason?: string | null
}

/**
 * Status badge for a strings-table row.
 * @param status - Row status.
 * @param reason - Untranslatable reason, shown as a tooltip.
 * @returns The badge.
 */
export function StatusBadge({ status, reason }: StatusBadgeProps) {
    const { label, className } = statusToChip(status)
    const title = status === "untranslatable" && reason ? reason : undefined
    return (
        <span className={`status-badge ${className}`} title={title}>
            {label}
        </span>
    )
}
