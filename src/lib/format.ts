/** Live position of a long dashboard task, such as a refresh that walks every mod. */
export interface TaskProgress {
    /** 1-based position of the item being worked on. */
    current: number
    /** Number of items in the task. */
    total: number
}

/**
 * Label for a dashboard button that runs a long task: the idle label, then "Verb..." while starting, then "Verb (3/5)..." once a count is known.
 *
 * @param idleLabel Label shown while the task is not running, e.g. "Refresh".
 * @param busyVerb Verb shown while it runs, e.g. "Refreshing".
 * @param busy Whether the task is running.
 * @param progress Current position, or null before the first item starts.
 * @returns The button label.
 */
export function progressLabel(idleLabel: string, busyVerb: string, busy: boolean, progress: TaskProgress | null): string {
    if (!busy) return idleLabel
    return progress ? `${busyVerb} (${progress.current}/${progress.total})\u2026` : `${busyVerb}\u2026`
}
