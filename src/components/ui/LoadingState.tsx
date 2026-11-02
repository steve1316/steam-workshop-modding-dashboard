/** Props for LoadingState. */
interface LoadingStateProps {
    /** Text shown while loading, e.g. "Loading mod details...". */
    message: string
}

/**
 * Centered, pulsing loading message used while a page fetches its data.
 *
 * @param message Loading text.
 * @returns The loading state.
 */
export default function LoadingState({ message }: LoadingStateProps) {
    return (
        <div className="loading-state" role="status">
            <h2>{message}</h2>
        </div>
    )
}
