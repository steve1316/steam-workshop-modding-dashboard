import { useEffect, useState } from "react"
import { getCurrentRun } from "@/games/total_war_warhammer_3/lib/registryApi"
import { type RunState } from "@/games/total_war_warhammer_3/lib/types"

const INTERVAL_MS = 2000

let currentState: RunState = { status: "idle" }
const subscribers = new Set<(s: RunState) => void>()
let intervalId: number | null = null

const tick = async () => {
    try {
        currentState = await getCurrentRun()
    } catch {
        currentState = { status: "idle" }
    }
    subscribers.forEach((cb) => cb(currentState))
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
    const [state, setState] = useState<RunState>(currentState)

    useEffect(() => {
        subscribers.add(setState)
        if (subscribers.size === 1) startPolling()
        // Avoid waiting up to INTERVAL_MS for the first update.
        setState(currentState)
        return () => {
            subscribers.delete(setState)
            if (subscribers.size === 0) stopPolling()
        }
    }, [])

    return state
}

/** Test-only: reset the module singleton between tests. */
export function _resetUseCurrentRunForTests() {
    stopPolling()
    subscribers.clear()
    currentState = { status: "idle" }
}
