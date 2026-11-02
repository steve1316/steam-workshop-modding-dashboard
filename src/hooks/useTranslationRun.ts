import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { useIterativeTranslation, type BatchDescriptor, type BatchState } from "@/hooks/useIterativeTranslation"
import { usePendingSuggestions, type SuggestionsBanner } from "@/hooks/usePendingSuggestions"
import { settingsQuery } from "@/lib/queryClient"

/** The fields every game's translate preview returns. */
export interface RunPreview {
    total_strings: number
    batch_plan?: BatchDescriptor[]
    message?: string
}

/** Options for `useTranslationRun`. */
export interface TranslationRunOptions {
    gameId: string
    modId: string
    /** Fired after each batch with its translations and the provider that made them. */
    onBatchTranslated: (translations: Record<string, string>, provider: string) => void
    /** Open the review as soon as a batch pauses, rather than showing the paused banner first. */
    autoOpenReview?: boolean
    /** Fired once when a batch pauses for review, or the run completes or fails. */
    onSettled?: (state: BatchState) => void
}

/**
 * One mod's translation run: the provider, the preview and confirm step, the batch loop, the review between batches, pending suggestions and
 * the result banner.
 *
 * @param options The game, mod and page callbacks.
 * @returns The run's state, actions, and props for the banner, paused banner and review modal.
 */
export function useTranslationRun<P extends RunPreview>({ gameId, modId, onBatchTranslated, autoOpenReview = false, onSettled }: TranslationRunOptions) {
    const { data: settings } = useQuery(settingsQuery)
    const [pickedProvider, setProvider] = useState<string | null>(null)
    const provider = pickedProvider ?? (typeof settings?.provider === "string" ? settings.provider : "")
    const [preview, setPreview] = useState<{ data: P; provider: string } | null>(null)
    // The user's last open or close of the review, tied to the paused batch it applies to. A new pause falls back to `autoOpenReview`.
    const [reviewChoice, setReviewChoice] = useState<{ state: BatchState; open: boolean } | null>(null)

    // Read the page's callbacks through refs so the batch loop and the phase effect stay stable while the page re-renders.
    const callbacksRef = useRef({ onBatchTranslated, onSettled })
    useEffect(() => {
        callbacksRef.current = { onBatchTranslated, onSettled }
    })
    const runProviderRef = useRef("")
    const batchTranslated = useCallback((translations: Record<string, string>) => callbacksRef.current.onBatchTranslated(translations, runProviderRef.current), [])
    const { state, startTranslation, continueAfterReview, cancel } = useIterativeTranslation(gameId, modId, batchTranslated)
    const stateRef = useRef(state)
    useEffect(() => {
        stateRef.current = state
    })

    // Each banner remembers the run state it was set in. A failed run shows its error until a later banner replaces it or it is dismissed.
    const [stored, setStored] = useState<{ banner: SuggestionsBanner | null; state: BatchState } | null>(null)
    const setBanner = useCallback((banner: SuggestionsBanner | null) => setStored({ banner, state: stateRef.current }), [])
    const runError: SuggestionsBanner | null =
        state.phase === "error" ? { type: "error", message: `${state.message}${state.completedBatches > 0 ? ` ${state.completedBatches} batch(es) completed before the error.` : ""}` } : null
    const banner = runError && stored?.state !== state ? runError : (stored?.banner ?? null)
    const pending = usePendingSuggestions(gameId, modId, setBanner)

    const handledRef = useRef<BatchState | null>(null)
    const { refresh } = pending
    useEffect(() => {
        if (state.phase === "idle" || state.phase === "translating" || handledRef.current === state) return
        handledRef.current = state
        if (state.phase !== "reviewing") refresh()
        callbacksRef.current.onSettled?.(state)
    }, [state, refresh])

    /**
     * Fetch a run's preview, which opens the confirm modal.
     *
     * @param chosen Provider for this run, or "" for the current one.
     * @param load The game's preview call.
     * @param labels Banner text when nothing needs translating, and the prefix for a failed preview.
     */
    const openPreview = async (chosen: string, load: (provider: string) => Promise<P>, labels: { empty?: string; failure?: string } = {}) => {
        const runProvider = chosen || provider
        setBanner(null)
        try {
            const data = await load(runProvider)
            if (data.total_strings === 0) {
                setBanner({ type: "success", message: data.message || labels.empty || "All strings are already translated." })
                return
            }
            setPreview({ data, provider: runProvider })
        } catch (err) {
            setBanner({ type: "error", message: `${labels.failure ?? "Preview failed"}: ${err instanceof Error ? err.message : String(err)}` })
        }
    }

    /**
     * Start the batch loop.
     *
     * @param runProvider Provider for the run.
     * @param plan Batches from the preview.
     * @param mode `"update"` revises changed rows.
     */
    const start = useCallback(
        (runProvider: string, plan: BatchDescriptor[], mode?: "translate" | "update") => {
            runProviderRef.current = runProvider
            setBanner(null)
            startTranslation(runProvider, plan, mode)
        },
        [startTranslation, setBanner]
    )

    /**
     * Close the confirm modal and start the run it previewed.
     *
     * @param begin Starts the run. Defaults to the preview's batch plan.
     */
    const confirmPreview = (begin?: (data: P, provider: string) => void) => {
        if (!preview) return
        setPreview(null)
        if (begin) begin(preview.data, preview.provider)
        else start(preview.provider, preview.data.batch_plan ?? [])
    }

    const reviewOpen = state.phase === "reviewing" && (reviewChoice?.state === state ? reviewChoice.open : autoOpenReview)

    return {
        banner,
        setBanner,
        pending,
        provider,
        setProvider,
        preview,
        openPreview,
        confirmPreview,
        closePreview: () => setPreview(null),
        state,
        start,
        continueAfterReview,
        cancel: () => {
            cancel()
            setBanner({ type: "success", message: "Translation cancelled." })
        },
        translating: state.phase === "translating" ? { batchIndex: state.batchIndex, totalBatches: state.totalBatches, streaming: state.streamingProgress } : null,
        pausedBanner:
            state.phase === "reviewing" && !reviewOpen
                ? {
                      batchIndex: state.batchIndex,
                      totalBatches: state.totalBatches,
                      onReview: () => setReviewChoice({ state, open: true }),
                      onContinue: continueAfterReview,
                      onCancel: () => {
                          cancel()
                          setBanner({ type: "success", message: `Translation cancelled. ${state.batchIndex} of ${state.totalBatches} batches completed.` })
                      },
                  }
                : null,
        review:
            state.phase === "reviewing" && reviewOpen
                ? {
                      suggestions: state.suggestions,
                      batchProgress: { current: state.batchIndex + 1, total: state.totalBatches },
                      onClose: () => setReviewChoice({ state, open: false }),
                      onContinue: continueAfterReview,
                  }
                : null,
    }
}
