import React, { useEffect, useState } from "react"

import { listApiResponses } from "@/games/total_war_warhammer_3/lib/translationApi"
import { ApiResponsesModal as SharedApiResponsesModal, type ApiResponseEntry } from "@/components/ApiResponsesModal"
import { toApiResponseEntry } from "@/components/ApiResponsesModal/helpers"

/** Props for `ApiResponsesModal`. */
interface ApiResponsesModalProps {
    workshopId: string
    onClose: () => void
}

/**
 * WH3 provider audit-log modal, a thin wrapper that maps WH3's api-responses onto the shared `ApiResponsesModal`.
 *
 * @param workshopId Translation mod Workshop id.
 * @param onClose Called when the modal closes.
 * @returns The modal.
 */
const ApiResponsesModal: React.FC<ApiResponsesModalProps> = ({ workshopId, onClose }) => {
    const [entries, setEntries] = useState<ApiResponseEntry[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const data = await listApiResponses(workshopId)
                if (!cancelled) {
                    setEntries(data.map(toApiResponseEntry))
                }
            } catch (e) {
                if (!cancelled) setError((e as Error).message)
            } finally {
                if (!cancelled) setLoading(false)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [workshopId])

    return <SharedApiResponsesModal entries={entries} loading={loading} error={error} onClose={onClose} />
}

export default ApiResponsesModal
