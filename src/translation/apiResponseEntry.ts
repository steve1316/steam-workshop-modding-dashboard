import type { ApiLogEntry } from "../shared_types"
import type { ApiResponseEntry } from "./ApiResponsesModal"

/**
 * Map one backend log entry onto the modal's record.
 * @param e - Entry from `api-responses`.
 * @param index - Position in the list, which keeps ids unique for entries sharing a timestamp.
 * @returns The modal record.
 */
export function toApiResponseEntry(e: ApiLogEntry, index: number): ApiResponseEntry {
    return {
        id: `${e.timestamp}-${index}`,
        kind: e.kind,
        timestamp: e.timestamp,
        model: e.model,
        inputTokens: e.input_tokens,
        outputTokens: e.output_tokens,
        costUsd: e.cost_usd,
        keysOrInputs: e.keys_or_inputs,
        rawText: e.raw_response,
    }
}
