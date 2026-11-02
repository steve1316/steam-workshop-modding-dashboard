import { useCallback, useEffect, useRef, useState } from "react"

import type { TaskProgress } from "@/dashboard/progressLabel"
import type { WH3RescanSummary } from "@/shared_types"
import { rescanMod } from "@/games/total_war_warhammer_3/translationApi"

/** State and actions returned by `useRescanAll`. */
export interface RescanAll {
    /** Missing until that mod has been scanned this session. */
    progressByMod: Record<string, WH3RescanSummary | null>
    /** Null while idle. */
    progress: TaskProgress | null
    running: boolean
    /** Rescans mods one at a time, cancelling any running batch. Resolves to the failure count (0 when cancelled). */
    rescanAll: (ids: string[]) => Promise<number>
    /** Rescans one mod outside any batch. A failure leaves its card as it was. */
    rescanOne: (id: string) => Promise<void>
}

/**
 * Rescans WH3 translation mods one at a time for the dashboard's "n / total". A new batch or leaving the page cancels the running one.
 *
 * @returns Per-mod results, progress, and the rescan actions.
 */
export function useRescanAll(): RescanAll {
    const [progressByMod, setProgressByMod] = useState<Record<string, WH3RescanSummary | null>>({})
    const [progress, setProgress] = useState<TaskProgress | null>(null)
    const [running, setRunning] = useState(false)
    const controllerRef = useRef<AbortController | null>(null)
    const unmountedRef = useRef(false)

    useEffect(() => {
        unmountedRef.current = false
        return () => {
            unmountedRef.current = true
            controllerRef.current?.abort()
        }
    }, [])

    const rescanAll = useCallback(async (ids: string[]) => {
        if (unmountedRef.current) return 0
        controllerRef.current?.abort()
        const controller = new AbortController()
        controllerRef.current = controller
        setRunning(true)
        let failed = 0

        for (let i = 0; i < ids.length; i++) {
            const id = ids[i]
            setProgress({ current: i + 1, total: ids.length })
            try {
                const summary = await rescanMod(id, controller.signal)
                if (controller.signal.aborted) return 0
                setProgressByMod((prev) => ({ ...prev, [id]: summary }))
            } catch {
                if (controller.signal.aborted) return 0
                // The rest of the batch still runs.
                failed++
            }
        }

        controllerRef.current = null
        setRunning(false)
        setProgress(null)
        return failed
    }, [])

    const rescanOne = useCallback(async (id: string) => {
        try {
            const summary = await rescanMod(id)
            if (!unmountedRef.current) setProgressByMod((prev) => ({ ...prev, [id]: summary }))
        } catch {
            // The card keeps its previous result.
        }
    }, [])

    return { progressByMod, progress, running, rescanAll, rescanOne }
}
