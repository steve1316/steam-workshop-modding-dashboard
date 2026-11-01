import type { StepStatus } from "../../api"

const LABELS: Record<StepStatus, string> = {
    queued: "Waiting...",
    running: "In-Progress...",
    done: "✓ Done",
    skipped: "Up to date",
    failed: "✕ Failed",
}

/** Props for `StepIndicator`. */
interface Props {
    status: StepStatus
    className?: string
}

/**
 * Status pill standing in for a script's Run button while the `update` pipeline runs. Queued and running steps show a spinner.
 *
 * @param status Pipeline progress of the script.
 * @param className Extra classes.
 * @returns The status span.
 */
export default function StepIndicator({ status, className }: Props) {
    return (
        <span role="status" className={`btn btn-outline step-indicator step-indicator--${status}${className ? ` ${className}` : ""}`}>
            {(status === "queued" || status === "running") && <span className="step-indicator__spinner" aria-hidden="true" />}
            {LABELS[status]}
        </span>
    )
}
