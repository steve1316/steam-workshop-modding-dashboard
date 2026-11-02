import { FaExclamationTriangle } from "react-icons/fa"
import type { ValidationIssue } from "@/games/total_war_warhammer_3/lib/types"

/** Props for `ValidationBadge`. */
interface Props {
    /** Renders nothing when empty. */
    issues: ValidationIssue[]
}

/**
 * Inline warning badge for rows with unresolved validation issues.
 *
 * @param issues Issues affecting this row.
 * @returns A warning icon whose tooltip lists each message, or null when there are no issues.
 */
export default function ValidationBadge({ issues }: Props) {
    if (issues.length === 0) return null
    const label = `${issues.length} validation issue${issues.length === 1 ? "" : "s"}`
    const tooltip = issues.map((i) => i.message).join("\n")
    return (
        <span aria-label={label} title={tooltip} style={{ color: "var(--warning)", display: "inline-flex" }}>
            <FaExclamationTriangle />
        </span>
    )
}
