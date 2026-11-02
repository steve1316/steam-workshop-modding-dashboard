import { useMemo, useState } from "react"
import Modal from "@/components/ui/Modal"
import "@/components/ApiResponsesModal/styles.css"

/** One provider API-response record as the modal shows it. */
export interface ApiResponseEntry {
    id: string
    /** Call kind (e.g. "scan-terms"). Falls back to a Batch label. */
    kind?: string
    /** ISO timestamp. */
    timestamp?: string
    model: string
    /** Prompt token count, when reported. */
    inputTokens?: number | null
    /** Completion token count, when reported. */
    outputTokens?: number | null
    /** Estimated USD cost. */
    costUsd?: number | null
    /** Keys or inputs sent, when recorded. */
    keysOrInputs?: string[]
    rawText: string
}

/** Props for the shared `ApiResponsesModal`. */
interface ApiResponsesModalProps {
    /** Entries, newest first (the caller orders them). */
    entries: ApiResponseEntry[]
    loading?: boolean
    /** Fetch error to show. */
    error?: string | null
    onClose: () => void
}

/**
 * Shared audit-log viewer for recorded provider API calls. The caller fetches and maps its records, and a total-cost summary spans all entries.
 * @param entries - API-response records.
 * @param loading - Whether the caller is still fetching.
 * @param error - Error to display.
 * @param onClose - Close handler.
 * @returns The modal.
 */
export function ApiResponsesModal({ entries, loading, error, onClose }: ApiResponsesModalProps) {
    const [activeIdx, setActiveIdx] = useState(0)
    const active = useMemo(() => entries[activeIdx] ?? null, [entries, activeIdx])
    const totalCost = useMemo(() => entries.reduce((sum, e) => sum + (e.costUsd ?? 0), 0), [entries])

    return (
        <Modal title="API Responses" size="lg" fill onClose={onClose}>
            {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
            {loading && !error && <p>Loading...</p>}
            {!loading && !error && entries.length === 0 && <p style={{ color: "var(--text-dim)" }}>No API responses recorded yet.</p>}
            {entries.length > 0 && (
                <>
                    {totalCost > 0 && (
                        <div style={{ marginBottom: "0.75rem", fontSize: "0.85rem", color: "var(--text-dim)" }}>
                            Total cost across {entries.length} call{entries.length !== 1 ? "s" : ""}: <span style={{ fontWeight: 600, color: "var(--text-main)" }}>${totalCost.toFixed(4)}</span>
                        </div>
                    )}
                    <div style={{ display: "flex", gap: "1rem", flex: 1, minHeight: 0 }}>
                        <div className="api-response-sidebar">
                            {entries.map((e, i) => (
                                <button key={e.id} type="button" className={`api-response-tab${i === activeIdx ? " active" : ""}`} data-testid="api-response-tab" onClick={() => setActiveIdx(i)}>
                                    <div className="api-response-kind">{e.kind ?? `Batch ${i + 1}`}</div>
                                    <div className="api-response-time">{e.timestamp ? new Date(e.timestamp).toLocaleString() : e.model}</div>
                                </button>
                            ))}
                        </div>
                        <div className="api-response-detail">
                            {active && (
                                <>
                                    <dl className="api-response-meta">
                                        {active.timestamp && (
                                            <>
                                                <dt>Timestamp</dt>
                                                <dd>{new Date(active.timestamp).toLocaleString()}</dd>
                                            </>
                                        )}
                                        <dt>Model</dt>
                                        <dd>{active.model}</dd>
                                        <dt>Tokens (in / out)</dt>
                                        <dd>
                                            {active.inputTokens ?? "-"} / {active.outputTokens ?? "-"}
                                        </dd>
                                        <dt>Cost (USD)</dt>
                                        <dd>{active.costUsd != null ? `$${active.costUsd.toFixed(4)}` : "-"}</dd>
                                        {active.keysOrInputs && active.keysOrInputs.length > 0 && (
                                            <>
                                                <dt>Keys / Inputs</dt>
                                                <dd>{active.keysOrInputs.join(", ")}</dd>
                                            </>
                                        )}
                                    </dl>
                                    <pre className="api-response-raw">{active.rawText}</pre>
                                </>
                            )}
                        </div>
                    </div>
                </>
            )}
        </Modal>
    )
}
