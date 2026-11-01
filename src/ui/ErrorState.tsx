import type { ReactNode } from "react"

/** A button offered by an error state. */
interface ErrorAction {
    label: string
    onClick: () => void
}

/** Props for ErrorState. */
interface ErrorStateProps {
    title: string
    /** What happened and what the user can do. */
    message: ReactNode
    /** Optional recovery button, e.g. Back to Dashboard. */
    action?: ErrorAction
}

/**
 * Full-width error card for a page that could not load.
 *
 * @param title Heading.
 * @param message Explanation.
 * @param action Optional recovery button.
 * @returns The error state.
 */
export default function ErrorState({ title, message, action }: ErrorStateProps) {
    return (
        <div className="glass-card static error-state" role="alert">
            <h2>{title}</h2>
            <p>{message}</p>
            {action && (
                <button type="button" className="btn btn-outline" onClick={action.onClick}>
                    {action.label}
                </button>
            )}
        </div>
    )
}
