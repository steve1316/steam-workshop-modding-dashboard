import { useSyncExternalStore } from "react"
import { getCurrentRun } from "@/games/total_war_warhammer_3/lib/registryApi"
import { type RunState } from "@/games/total_war_warhammer_3/lib/types"

const INTERVAL_MS = 2000

let currentState: RunState = { status: "idle" }
const listeners = new Set<() => void>()
let intervalId: number | null = null

const tick = async () => {
    try {
        currentState = await getCurrentRun()
    } catch {
        currentState = { status: "idle" }
    }
    listeners.forEach((listener) => listener())
    if (currentState.status === "idle") stopPolling()
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
 * Register a listener for run-state changes. The first listener starts the poll and the last one to leave stops it.
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

/** Resume polling immediately. Call after a run is launched so the next state change is observed. */
export function kickPoll() {
    startPolling()
}

/**
 * Latest TW3 run state. The poll is shared across callers, so many mounted hooks still make one `GET /run` per `INTERVAL_MS`.
 *
 * @returns The run state, idle until the first poll completes.
 */
export function useCurrentRun(): RunState {
    return useSyncExternalStore(subscribe, () => currentState)
}

/** Test-only: reset the module singleton between tests. */
export function _resetUseCurrentRunForTests() {
    stopPolling()
    listeners.clear()
    currentState = { status: "idle" }
}
