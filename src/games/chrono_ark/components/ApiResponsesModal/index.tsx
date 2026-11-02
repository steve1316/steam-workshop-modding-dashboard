import { useQuery } from "@tanstack/react-query"
import { fetchJson, gameApi } from "@/lib/api"
import type { ApiLogEntry } from "@/lib/types"
import { ApiResponsesModal as SharedApiResponsesModal } from "@/components/ApiResponsesModal"
import { toApiResponseEntry } from "@/components/ApiResponsesModal/helpers"

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
    const { data, isPending, error } = useQuery({
        queryKey: ["chrono_ark", "api-responses", modId],
        queryFn: () => fetchJson<ApiLogEntry[]>(gameApi("chrono_ark").url(`/mods/${modId}/api-responses`)),
    })

    return <SharedApiResponsesModal entries={(data ?? []).map(toApiResponseEntry)} loading={isPending} error={error?.message ?? null} onClose={onClose} />
}
