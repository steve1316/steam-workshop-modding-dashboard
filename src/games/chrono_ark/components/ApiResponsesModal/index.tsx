import { useEffect, useState } from "react"
import { gameApi } from "../../../../api/games"
import type { ApiLogEntry } from "../../../../shared_types"
import { ApiResponsesModal as SharedApiResponsesModal, type ApiResponseEntry } from "../../../../translation/ApiResponsesModal"
import { toApiResponseEntry } from "../../../../translation/apiResponseEntry"

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
                const data: ApiLogEntry[] = await res.json()
                if (!cancelled) setEntries(data.map(toApiResponseEntry))
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
