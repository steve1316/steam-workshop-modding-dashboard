import { useState } from "react"
import type { ValidationIssue } from "@/games/total_war_warhammer_3/api"

/** Props for ValidationPanel. */
interface Props {
    /** Null before the first fetch completes. */
    issues: ValidationIssue[] | null
    /** Resolves once the new results are broadcast. */
    onRefresh: () => Promise<void>
}

/**
 * Cross-reference report shown above the Supported Mods grid. Groups issues by kind, with missing mod paths expanded and effect categories collapsed.
 *
 * @param issues Latest issues from `useValidation`, null before the first fetch.
 * @param onRefresh Triggers a validation poll.
 * @returns The panel, or null while loading or when everything resolves.
 */
const ValidationPanel = ({ issues, onRefresh }: Props) => {
    const [refreshing, setRefreshing] = useState(false)

    if (!issues || issues.length === 0) return null

    const pathIssues = issues.filter((i) => i.kind === "missing_mod_path")
    const effectIssues = issues.filter((i) => i.kind === "missing_effect_category")

    const handleRefresh = async () => {
        setRefreshing(true)
        try {
            await onRefresh()
        } finally {
            setRefreshing(false)
        }
    }

    return (
        <div className="glass-card" style={{ padding: "1rem", marginBottom: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
                    <h3 style={{ margin: 0 }}>Validation</h3>
                    <span style={{ fontSize: "0.85rem", color: "var(--warning)" }}>
                        {issues.length} issue{issues.length === 1 ? "" : "s"}
                    </span>
                </div>
                <button className="btn btn-outline" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>
            <p style={{ margin: "0.5rem 0 0", color: "var(--text-dim)", fontSize: "0.9rem" }}>
                Broken references in <code>SUPPORTED_MODS</code>: a mod whose <code>path</code> no longer exists on disk, or a <code>modified_attributes</code> entry with no matching category in{" "}
                <code>SUPPORTED_EFFECTS</code>.
            </p>

            {pathIssues.length > 0 && (
                <details open>
                    <summary style={{ cursor: "pointer", padding: "0.5rem 0", fontWeight: 600 }}>Missing mod paths ({pathIssues.length})</summary>
                    {pathIssues.map((issue) => (
                        <IssueRow key={`${issue.mod_package_name}:${issue.target}`} issue={issue} />
                    ))}
                </details>
            )}

            {effectIssues.length > 0 && (
                <details>
                    <summary style={{ cursor: "pointer", padding: "0.5rem 0", fontWeight: 600 }}>Missing effect categories ({effectIssues.length})</summary>
                    {effectIssues.map((issue) => (
                        <IssueRow key={`${issue.mod_package_name}:${issue.target}`} issue={issue} />
                    ))}
                </details>
            )}
        </div>
    )
}

/** Props for IssueRow. */
interface IssueRowProps {
    issue: ValidationIssue
}

/**
 * One issue entry with the mod name, broken reference, and message.
 *
 * @param issue Issue to display.
 * @returns The row.
 */
function IssueRow({ issue }: IssueRowProps) {
    return (
        <div style={{ padding: "0.5rem 0.75rem", marginTop: "0.5rem", borderLeft: "2px solid var(--warning)", background: "rgba(255,255,255,0.03)", borderRadius: 4 }}>
            <div style={{ fontWeight: 600 }}>{issue.mod_name}</div>
            {issue.target && <code style={{ display: "block", margin: "0.25rem 0", color: "var(--text-dim)", fontSize: "0.85rem", wordBreak: "break-all" }}>{issue.target}</code>}
            <div style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>{issue.message}</div>
        </div>
    )
}

export default ValidationPanel
