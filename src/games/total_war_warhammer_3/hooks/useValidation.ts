import { useSyncExternalStore } from "react"
import { fetchValidation, RegistryError } from "@/games/total_war_warhammer_3/lib/registryApi"
import { type ValidationIssue } from "@/games/total_war_warhammer_3/lib/types"

const INTERVAL_MS = 5000

/** The shared poll result, replaced on each tick. */
interface Snapshot {
    /** Null before the first successful fetch. */
    issues: ValidationIssue[] | null
    /** Null after a successful fetch. */
    error: RegistryError | null
}

const EMPTY: Snapshot = { issues: null, error: null }
let snapshot: Snapshot = EMPTY
let intervalId: number | null = null
const listeners = new Set<() => void>()

const tick = async (): Promise<void> => {
    try {
        snapshot = { issues: await fetchValidation(), error: null }
    } catch (err) {
        // Wrap non-registry errors so the UI leaves loading state and can show a banner.
        const error = err instanceof RegistryError ? err : new RegistryError(0, err instanceof Error ? err.message : "Unknown error during validation fetch", null)
        // Keep the issues on failure so the UI shows its last good data.
        snapshot = { issues: snapshot.issues, error }
    }
    listeners.forEach((listener) => listener())
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

/**
 * Register a listener for poll results. The first listener starts the poll and the last one to leave stops it.
 *
 * @param listener Called after every poll.
 * @returns The unsubscribe function.
 */
function subscribe(listener: () => void): () => void {
    listeners.add(listener)
    if (listeners.size === 1) startPolling()
    return () => {
        listeners.delete(listener)
        if (listeners.size === 0) stopPolling()
    }
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
    const snap = useSyncExternalStore(subscribe, () => snapshot)

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
    listeners.clear()
    snapshot = EMPTY
}
