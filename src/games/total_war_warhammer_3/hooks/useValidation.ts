import { useEffect, useState } from "react"
import { fetchValidation, RegistryError, type ValidationIssue } from "@/games/total_war_warhammer_3/lib/registryApi"

const INTERVAL_MS = 5000

let latestIssues: ValidationIssue[] | null = null
let latestError: RegistryError | null = null
let intervalId: number | null = null

/** Broadcast to every subscriber on each tick. */
interface Snapshot {
    /** Null before the first successful fetch. */
    issues: ValidationIssue[] | null
    /** Null after a successful fetch. */
    error: RegistryError | null
}

const subscribers = new Set<(snap: Snapshot) => void>()

const broadcast = () => {
    const snap: Snapshot = { issues: latestIssues, error: latestError }
    subscribers.forEach((cb) => cb(snap))
}

const tick = async (): Promise<void> => {
    try {
        latestIssues = await fetchValidation()
        latestError = null
    } catch (err) {
        if (err instanceof RegistryError) {
            latestError = err
        } else {
            // Wrap non-registry errors so the UI leaves loading state and can show a banner.
            const detail = err instanceof Error ? err.message : "Unknown error during validation fetch"
            latestError = new RegistryError(0, detail, null)
        }
        // Keep latestIssues on failure so the UI shows its last good data.
    }
    broadcast()
}

const startPolling = () => {
    if (intervalId !== null) return
    tick()
    intervalId = window.setInterval(tick, INTERVAL_MS)
}

const stopPolling = () => {
    if (intervalId === null) return
    window.clearInterval(intervalId)
    intervalId = null
}

/** Return shape of `useValidation`. */
interface UseValidationResult {
    /** Null before the first fetch. */
    issues: ValidationIssue[] | null
    /** True until the first response (no data and no error yet). */
    loading: boolean
    /** Cleared on the next success. */
    error: RegistryError | null
    /** Polls immediately and broadcasts the result to all subscribers. */
    refresh: () => Promise<void>
}

/**
 * Latest TW3 FK validation issues. The poll is shared across callers, so many mounted hooks make one request per `INTERVAL_MS`.
 *
 * @returns The issues, loading flag, error, and a `refresh` callback.
 */
export function useValidation(): UseValidationResult {
    const [snap, setSnap] = useState<Snapshot>({ issues: latestIssues, error: latestError })

    useEffect(() => {
        subscribers.add(setSnap)
        if (subscribers.size === 1) startPolling()
        // Avoid waiting up to INTERVAL_MS for the first update.
        setSnap({ issues: latestIssues, error: latestError })
        return () => {
            subscribers.delete(setSnap)
            if (subscribers.size === 0) stopPolling()
        }
    }, [])

    return {
        issues: snap.issues,
        error: snap.error,
        loading: snap.issues === null && snap.error === null,
        refresh: tick,
    }
}

/** Test-only: reset the module singleton between tests. */
export function _resetUseValidationForTests() {
    stopPolling()
    subscribers.clear()
    latestIssues = null
    latestError = null
}
