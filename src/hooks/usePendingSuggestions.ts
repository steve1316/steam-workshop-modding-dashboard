import { useCallback, useEffect, useState } from "react"

import { gameApi } from "@/lib/api"
import type { TermSuggestion } from "@/lib/types"

/** A result message for the page's feedback banner. */
export interface SuggestionsBanner {
    type: "success" | "error"
    message: string
}

/** What `usePendingSuggestions` returns. */
export interface PendingSuggestions {
    suggestions: TermSuggestion[]
    /** Re-fetch the pending list. */
    refresh: () => Promise<void>
    /** Scan the mod for new terms, refresh the list, and report through the banner callback. */
    scan: () => Promise<void>
    scanning: boolean
}

/**
 * Pending glossary suggestions for one mod. Loads on mount and runs the Scan for Terms flow.
 *
 * @param gameId - Backend game id, e.g. "chrono_ark".
 * @param modId - Mod's id.
 * @param onBanner - Receives the scan result or error.
 * @returns The list, `refresh`, `scan` and the scanning flag.
 */
export function usePendingSuggestions(gameId: string, modId: string, onBanner: (banner: SuggestionsBanner) => void): PendingSuggestions {
    const [suggestions, setSuggestions] = useState<TermSuggestion[]>([])
    const [scanning, setScanning] = useState(false)

    const refresh = useCallback(async () => {
        if (!modId) return
        try {
            const res = await gameApi(gameId).get(`/mods/${modId}/glossary/suggestions`)
            if (!res.ok) return
            const data = await res.json()
            setSuggestions(Array.isArray(data) ? data : [])
        } catch {
            /* keep the last known list */
        }
    }, [gameId, modId])

    useEffect(() => {
        refresh()
    }, [refresh])

    const scan = useCallback(async () => {
        setScanning(true)
        try {
            const res = await gameApi(gameId).post(`/mods/${modId}/glossary/suggestions/scan`)
            const data = await res.json().catch(() => ({}))
            if (!res.ok) {
                onBanner({ type: "error", message: `Scan failed: ${data.detail || res.statusText || "Unknown error"}` })
                return
            }
            if (data.new > 0) {
                await refresh()
                onBanner({ type: "success", message: `Found ${data.new} new glossary term suggestion(s).` })
            } else {
                onBanner({ type: "success", message: "No new glossary terms found." })
            }
        } catch (err) {
            onBanner({ type: "error", message: `Scan failed: ${(err as Error).message}` })
        } finally {
            setScanning(false)
        }
    }, [gameId, modId, onBanner, refresh])

    return { suggestions, refresh, scan, scanning }
}
