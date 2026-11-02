import React from "react"
import { useQuery } from "@tanstack/react-query"

import { listApiResponses } from "@/games/total_war_warhammer_3/lib/translationApi"
import { ApiResponsesModal as SharedApiResponsesModal } from "@/components/ApiResponsesModal"
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
    const { data, isPending, error } = useQuery({ queryKey: ["total_war_warhammer_3", "api-responses", workshopId], queryFn: () => listApiResponses(workshopId) })

    return <SharedApiResponsesModal entries={(data ?? []).map(toApiResponseEntry)} loading={isPending} error={error?.message ?? null} onClose={onClose} />
}

export default ApiResponsesModal
