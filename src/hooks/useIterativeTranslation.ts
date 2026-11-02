import { useState, useRef, useCallback } from "react"
import { API_BASE, gameApi } from "@/lib/api"
import { readEventStream } from "@/lib/stream"
import type { TermSuggestion } from "@/lib/types"

/** Descriptor for a single batch, provided by the preview endpoint's `batch_plan`. */
export type BatchDescriptor = {
    source_lang: string
    keys: string[]
    size: number
}

/** Possible phases of the iterative batch translation state machine. */
export type BatchPhase = "idle" | "translating" | "reviewing" | "complete" | "error"

/** Real-time progress from a streaming provider (e.g. Ollama). */
export type StreamingProgress = {
    tokensGenerated: number
    elapsedSec: number
    tokensPerSec: number
}

/** Full state exposed by the hook. */
export type BatchState =
    | { phase: "idle" }
    | { phase: "translating"; batchIndex: number; totalBatches: number; streamingProgress?: StreamingProgress }
    | { phase: "reviewing"; batchIndex: number; totalBatches: number; suggestions: TermSuggestion[] }
    | { phase: "complete"; totalTranslated: number }
    | { phase: "error"; message: string; completedBatches: number }

/** Providers that support real-time streaming progress. */
const STREAMING_PROVIDERS = new Set(["ollama", "llamacpp"])

/** Providers whose server should be stopped after translation to free GPU memory. */
const STOP_AFTER_PROVIDERS = new Set(["llamacpp"])

/**
 * Manage iterative per-batch translation with glossary review between batches.
 *
 * `startTranslation` takes the preview's batch plan (`mode` `"update"` revises changed rows). A batch with suggestions moves to "reviewing"
 * until `continueAfterReview` is called.
 *
 * @param gameId - Routes translate API calls, e.g. "chrono_ark"
 * @param modId - Mod being translated
 * @param onBatchTranslated - Fired after each batch with the new translations
 */
export function useIterativeTranslation(gameId: string, modId: string, onBatchTranslated: (translations: Record<string, string>) => void) {
    const [state, setState] = useState<BatchState>({ phase: "idle" })
    const [batchTranslations, setBatchTranslations] = useState<Record<string, string>>({})

    const planRef = useRef<BatchDescriptor[]>([])
    const providerRef = useRef<string>("")
    const modeRef = useRef<"translate" | "update">("translate")
    const cancelledRef = useRef(false)
    const abortControllerRef = useRef<AbortController | null>(null)
    const totalTranslatedRef = useRef(0)
    // Breaks the circular dependency between translateBatch and handleBatchResult.
    const translateBatchRef = useRef<(batchIndex: number) => Promise<void>>(undefined)

    /** Stop the llama-server process after translation to free GPU memory. */
    const stopProviderIfNeeded = useCallback(() => {
        if (STOP_AFTER_PROVIDERS.has(providerRef.current)) {
            fetch(`${API_BASE}/llamacpp/stop`, { method: "POST" }).catch(() => {})
        }
    }, [])

    /** Handle a completed batch result (shared by streaming and non-streaming paths). */
    const handleBatchResult = useCallback(
        (batchIndex: number, totalBatches: number, newTranslations: Record<string, string>, suggestions: TermSuggestion[]) => {
            totalTranslatedRef.current += Object.keys(newTranslations).length
            setBatchTranslations((prev) => ({ ...prev, ...newTranslations }))
            onBatchTranslated(newTranslations)

            const isLastBatch = batchIndex >= totalBatches - 1

            if (isLastBatch) {
                if (suggestions.length > 0) {
                    setState({ phase: "reviewing", batchIndex, totalBatches, suggestions })
                } else {
                    stopProviderIfNeeded()
                    setState({ phase: "complete", totalTranslated: totalTranslatedRef.current })
                }
            } else if (suggestions.length > 0) {
                setState({ phase: "reviewing", batchIndex, totalBatches, suggestions })
            } else {
                translateBatchRef.current?.(batchIndex + 1)
            }
        },
        [onBatchTranslated]
    )

    /** Translate a batch via SSE streaming (real-time progress). */
    const translateBatchStreaming = useCallback(
        async (batchIndex: number, totalBatches: number) => {
            const batch = planRef.current[batchIndex]

            try {
                const controller = new AbortController()
                abortControllerRef.current = controller

                const res = await gameApi(gameId).post(
                    "/translate/batch/stream",
                    {
                        mod_id: modId,
                        provider: providerRef.current,
                        keys: batch.keys,
                        source_lang: batch.source_lang,
                        is_first_batch: batchIndex === 0,
                    },
                    { signal: controller.signal }
                )

                if (cancelledRef.current) return

                if (!res.ok) {
                    const data = await res.json().catch(() => ({ detail: "Translation failed" }))
                    setState({ phase: "error", message: data.detail || "Translation failed", completedBatches: batchIndex })
                    return
                }

                await readEventStream(res, (event) => {
                    if (cancelledRef.current) return true
                    if (event.type === "progress") {
                        setState({
                            phase: "translating",
                            batchIndex,
                            totalBatches,
                            streamingProgress: {
                                tokensGenerated: event.tokens_generated as number,
                                elapsedSec: event.elapsed_sec as number,
                                tokensPerSec: event.tokens_per_sec as number,
                            },
                        })
                    } else if (event.type === "complete") {
                        handleBatchResult(batchIndex, totalBatches, (event.translations as Record<string, string>) || {}, (event.suggestions as TermSuggestion[]) || [])
                    } else if (event.type === "error") {
                        setState({ phase: "error", message: event.message as string, completedBatches: batchIndex })
                    }
                })
            } catch (err) {
                if (cancelledRef.current) return
                setState({
                    phase: "error",
                    message: err instanceof Error ? err.message : "Translation failed. Could not reach the server.",
                    completedBatches: batchIndex,
                })
            }
        },
        [gameId, modId, handleBatchResult]
    )

    const translateBatch = useCallback(
        async (batchIndex: number) => {
            if (cancelledRef.current) return

            const plan = planRef.current
            const batch = plan[batchIndex]
            const totalBatches = plan.length

            setState({ phase: "translating", batchIndex, totalBatches })

            if (STREAMING_PROVIDERS.has(providerRef.current)) {
                return translateBatchStreaming(batchIndex, totalBatches)
            }

            try {
                const res = await gameApi(gameId).post("/translate/batch", {
                    mod_id: modId,
                    mode: modeRef.current,
                    provider: providerRef.current,
                    keys: batch.keys,
                    source_lang: batch.source_lang,
                    is_first_batch: batchIndex === 0,
                })

                if (cancelledRef.current) return

                const data = await res.json()
                if (!res.ok) {
                    setState({
                        phase: "error",
                        message: data.detail || "Translation failed",
                        completedBatches: batchIndex,
                    })
                    return
                }

                handleBatchResult(batchIndex, totalBatches, data.translations || {}, data.suggestions || [])
            } catch (err) {
                if (cancelledRef.current) return
                setState({
                    phase: "error",
                    message: err instanceof Error ? err.message : "Translation failed. Could not reach the server.",
                    completedBatches: batchIndex,
                })
            }
        },
        [gameId, modId, translateBatchStreaming, handleBatchResult]
    )

    // Lets handleBatchResult call translateBatch for auto-advance.
    translateBatchRef.current = translateBatch

    const startTranslation = useCallback(
        (provider: string, batchPlan: BatchDescriptor[], mode: "translate" | "update" = "translate") => {
            planRef.current = batchPlan
            providerRef.current = provider
            modeRef.current = mode
            cancelledRef.current = false
            totalTranslatedRef.current = 0
            setBatchTranslations({})
            translateBatch(0)
        },
        [translateBatch]
    )

    const continueAfterReview = useCallback(() => {
        const plan = planRef.current
        if (state.phase !== "reviewing") return

        const nextIndex = state.batchIndex + 1
        if (nextIndex >= plan.length) {
            stopProviderIfNeeded()
            setState({ phase: "complete", totalTranslated: totalTranslatedRef.current })
        } else {
            translateBatch(nextIndex)
        }
    }, [state, translateBatch])

    const cancel = useCallback(() => {
        cancelledRef.current = true
        abortControllerRef.current?.abort()
        abortControllerRef.current = null
        // Tell the backend to cancel so it closes the active connection.
        gameApi(gameId)
            .post(`/translate/cancel?mod_id=${encodeURIComponent(modId)}`)
            .catch(() => {})
        stopProviderIfNeeded()
        setState({ phase: "idle" })
    }, [gameId, modId, stopProviderIfNeeded])

    return {
        state,
        startTranslation,
        continueAfterReview,
        cancel,
        batchTranslations,
    }
}
