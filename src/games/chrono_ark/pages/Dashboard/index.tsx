import React, { useState, useMemo, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useGameSlug } from "@/hooks/useGameSlug"
import ModGrid from "@/games/chrono_ark/components/ModGrid"
import EstimateTotalCostModal from "@/games/chrono_ark/components/EstimateTotalCostModal"
import type { ModStatus } from "@/games/chrono_ark/lib/types"
import { gameApi } from "@/lib/api"
import { filterMods } from "@/games/chrono_ark/lib/search"
import DashboardHeader from "@/components/Dashboard/DashboardHeader"
import DashboardSection from "@/components/Dashboard/DashboardSection"
import { progressLabel } from "@/lib/format"
import { useCardWidth } from "@/hooks/useCardWidth"
import { rememberScrollTarget, useScrollRestore } from "@/hooks/useScrollRestore"
import Banner from "@/components/ui/Banner"

/**
 * Grid of all mods and their translation progress.
 *
 * @returns The dashboard page.
 */
const DashboardPage: React.FC = () => {
    const navigate = useNavigate()
    const slug = useGameSlug()
    // `null` until the first fetch settles, so the grid can show a skeleton instead of an empty page.
    const [mods, setMods] = useState<ModStatus[] | null>(null)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [refreshError, setRefreshError] = useState<string | null>(null)
    // True once any mod list has arrived. After that a failed fetch keeps the cards and shows a banner instead.
    const hasLoadedRef = useRef(false)
    const [search, setSearch] = useState("")
    const [refreshing, setRefreshing] = useState(false)
    const [refreshProgress, setRefreshProgress] = useState<{ current: number; total: number; mod_name: string } | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const gridWrapperRef = useRef<HTMLDivElement>(null)
    const [estimating, setEstimating] = useState(false)
    const [estimateProgress, setEstimateProgress] = useState<{ current: number; total: number; mod_name: string } | null>(null)
    const [estimateResults, setEstimateResults] = useState<
        {
            mod_id: string
            mod_name: string
            total_strings: number
            provider: string
            estimates: Record<string, { estimated_input_tokens: number; estimated_output_tokens: number; estimated_cost_usd: number; model: string; note: string }>
        }[]
    >([])
    const [showEstimateModal, setShowEstimateModal] = useState(false)
    const estimateAbortRef = useRef<AbortController | null>(null)

    /** Load the mod list. A failed first load shows an error with Retry, while later failures keep the cards and show a banner. */
    const fetchMods = async () => {
        try {
            const res = await gameApi("chrono_ark").get("/mods")
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data = await res.json()
            hasLoadedRef.current = true
            setMods(data)
            setLoadError(null)
        } catch (err) {
            console.error("Failed to fetch mods:", err)
            const message = (err as Error).message
            if (hasLoadedRef.current) setRefreshError(`Could not reload mods: ${message}`)
            else setLoadError(`Could not load mods: ${message}`)
        }
    }

    /** Clears the load error, which brings the skeleton back, and tries the first load again. */
    const retryLoad = () => {
        setLoadError(null)
        fetchMods()
    }

    useEffect(() => {
        fetchMods()
    }, [])

    /**
     * Rescan a mod's workshop folder, then reload the list.
     *
     * @param modId - Mod's Workshop id.
     */
    const handleModSync = async (modId: string) => {
        try {
            await gameApi("chrono_ark").post(`/mods/${modId}/sync`)
            fetchMods()
        } catch (err) {
            console.error("Failed to sync mod:", err)
        }
    }

    // Abort in-flight streams on unmount.
    useEffect(() => {
        return () => {
            abortRef.current?.abort()
            estimateAbortRef.current?.abort()
        }
    }, [])

    /** Re-extract every mod from scratch, streaming per-mod progress over SSE. A new run aborts the previous one. */
    const handleRefresh = async () => {
        abortRef.current?.abort()

        const controller = new AbortController()
        abortRef.current = controller

        setRefreshing(true)
        setRefreshProgress(null)
        setRefreshError(null)

        try {
            const res = await gameApi("chrono_ark").post("/mods/refresh", undefined, { signal: controller.signal })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const reader = res.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) return

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                const text = decoder.decode(value)
                for (const line of text.split("\n")) {
                    if (!line.startsWith("data: ")) continue
                    try {
                        const event = JSON.parse(line.slice(6))
                        if (event.done) {
                            hasLoadedRef.current = true
                            setMods(event.results)
                            setLoadError(null)
                        } else {
                            setRefreshProgress(event)
                        }
                    } catch {
                        /* skip malformed lines */
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name !== "AbortError") {
                console.error("Failed to refresh mods:", err)
                setRefreshError(`Refresh failed: ${(err as Error).message}`)
            }
        } finally {
            setRefreshing(false)
            setRefreshProgress(null)
            abortRef.current = null
        }
    }

    /** Estimate translation cost for every mod, streaming per-mod progress over SSE. A new run aborts the previous one. */
    const handleEstimate = async () => {
        estimateAbortRef.current?.abort()

        const controller = new AbortController()
        estimateAbortRef.current = controller

        setEstimating(true)
        setEstimateProgress(null)
        setEstimateResults([])

        try {
            const res = await gameApi("chrono_ark").post("/translate/estimate-all", undefined, { signal: controller.signal })
            const reader = res.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) return

            const accumulated: typeof estimateResults = []

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                const text = decoder.decode(value)
                for (const line of text.split("\n")) {
                    if (!line.startsWith("data: ")) continue
                    try {
                        const event = JSON.parse(line.slice(6))
                        if (event.done) {
                            setShowEstimateModal(true)
                        } else {
                            accumulated.push({
                                mod_id: event.mod_id,
                                mod_name: event.mod_name,
                                total_strings: event.total_strings,
                                provider: event.provider,
                                estimates: event.estimates,
                            })
                            setEstimateResults([...accumulated])
                            setEstimateProgress({ current: event.current, total: event.total, mod_name: event.mod_name })
                        }
                    } catch {
                        /* skip malformed lines */
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name !== "AbortError") {
                console.error("Failed to estimate costs:", err)
            }
        } finally {
            setEstimating(false)
            setEstimateProgress(null)
            estimateAbortRef.current = null
        }
    }

    const filteredMods = useMemo(() => filterMods(mods ?? [], search), [mods, search])

    // Scroll back to the card the user opened once the real list is on screen.
    useScrollRestore(mods !== null)

    // The search field matches the width of one card column.
    const cardWidth = useCardWidth(gridWrapperRef, filteredMods.length)

    /**
     * Remember the clicked mod for scroll restore, then open its detail page.
     *
     * @param modId - Mod's Workshop id.
     */
    const handleModSelect = (modId: string) => {
        rememberScrollTarget(modId)
        navigate(`/${slug}/translation/${modId}`)
    }

    return (
        <>
            <DashboardHeader
                title="Workshop Dashboard"
                tagline="Manage and translate your Chrono Ark mods"
                search={search}
                onSearchChange={setSearch}
                searchPlaceholder="Search by name or author..."
                searchWidth={cardWidth}
                actions={
                    <>
                        <button className="btn btn-outline" onClick={handleRefresh} disabled={refreshing}>
                            {progressLabel("Refresh", "Refreshing", refreshing, refreshProgress)}
                        </button>
                        <button className="btn btn-outline" onClick={handleEstimate} disabled={estimating || refreshing}>
                            {progressLabel("Estimate Total Cost", "Estimating", estimating, estimateProgress)}
                        </button>
                    </>
                }
            />

            {refreshError && (
                <Banner tone="error" onDismiss={() => setRefreshError(null)}>
                    {refreshError}
                </Banner>
            )}

            <div ref={gridWrapperRef}>
                <DashboardSection
                    loading={mods === null}
                    error={loadError}
                    onRetry={retryLoad}
                    empty={filteredMods.length === 0}
                    emptyMessage={search.trim() ? `No mods match "${search.trim()}".` : "No mods found."}
                >
                    <ModGrid mods={filteredMods} onModSelect={handleModSelect} onModSync={handleModSync} searchQuery={search.trim()} />
                </DashboardSection>
            </div>
            {showEstimateModal && <EstimateTotalCostModal results={estimateResults} onClose={() => setShowEstimateModal(false)} />}
        </>
    )
}

export default DashboardPage
