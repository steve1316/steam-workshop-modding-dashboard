import { useEffect, useState } from "react"
import { gameApi } from "../../../../api/games"
import { ApiResponsesModal as SharedApiResponsesModal, type ApiResponseEntry } from "../../../../translation/ApiResponsesModal"

/** One recorded provider API response for a Chrono Ark translation batch. */
interface CaApiResponse {
    model: string
    /** Prompt token count, when reported. */
    input_tokens?: number | null
    /** Completion token count, when reported. */
    output_tokens?: number | null
    /** Estimated USD cost, when available. */
    cost_usd?: number | null
    raw_text: string
}

/** Props for ApiResponsesModal. */
interface ApiResponsesModalProps {
    modId: string
    onClose: () => void
}

/**
 * Provider audit-log modal, a wrapper that fetches `api-responses` and maps them onto the shared `ApiResponsesModal`.
 * @param modId - Mod's Workshop id.
 * @param onClose - Close handler.
 * @returns The modal.
 */
export default function ApiResponsesModal({ modId, onClose }: ApiResponsesModalProps) {
    const [entries, setEntries] = useState<ApiResponseEntry[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const res = await gameApi("chrono_ark").get(`/mods/${modId}/api-responses`)
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                const data: CaApiResponse[] = await res.json()
                if (!cancelled) {
                    setEntries(data.map((e, i) => ({ id: String(i), model: e.model, inputTokens: e.input_tokens, outputTokens: e.output_tokens, costUsd: e.cost_usd, rawText: e.raw_text })))
                }
            } catch (err) {
                if (!cancelled) setError((err as Error).message)
            } finally {
                if (!cancelled) setLoading(false)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [modId])

    return <SharedApiResponsesModal entries={entries} loading={loading} error={error} onClose={onClose} />
}
