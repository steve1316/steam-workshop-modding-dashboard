import React from "react"
import Modal from "@/ui/Modal"

/** Per-mod cost estimate from the backend's bulk estimate endpoint, with one entry per target language. */
interface ModEstimate {
    mod_id: string
    mod_name: string
    /** Translatable strings across all languages. */
    total_strings: number
    /** e.g. `"OpenAI"`, `"Anthropic"`. */
    provider: string
    /** Keyed by language code. */
    estimates: Record<
        string,
        {
            /** Across all batches. */
            estimated_input_tokens: number
            /** Across all batches. */
            estimated_output_tokens: number
            /** In USD. */
            estimated_cost_usd: number
            /** e.g. `"gpt-4.1"`, `"claude-sonnet-5"`. */
            model: string
            /** e.g. `"Prices are approximate"`. */
            note: string
        }
    >
}

/** Props for {@link EstimateTotalCostModal}. */
interface EstimateTotalCostModalProps {
    results: ModEstimate[]
    onClose: () => void
}

/**
 * Read-only modal summarizing the cost estimate across all selected mods, with a per-mod breakdown.
 *
 * @param results - Per-mod cost estimates
 * @param onClose - Fires on Close or backdrop click
 * @returns The estimate modal
 */
const EstimateTotalCostModal: React.FC<EstimateTotalCostModalProps> = ({ results, onClose }) => {
    const grandTotalCost = results.reduce((sum, mod) => sum + Object.values(mod.estimates).reduce((s, e) => s + e.estimated_cost_usd, 0), 0)
    const grandTotalStrings = results.reduce((sum, mod) => sum + mod.total_strings, 0)

    // Provider and model come from the first mod that has estimates.
    const firstWithEstimates = results.find((m) => Object.keys(m.estimates).length > 0)
    const provider = firstWithEstimates?.provider ?? ""
    const model = firstWithEstimates ? (Object.values(firstWithEstimates.estimates)[0]?.model ?? "") : ""

    return (
        <Modal title="Estimate Total Cost" size="md" fill onClose={onClose}>
            <div style={{ display: "flex", gap: "1.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Provider</span>
                    <div style={{ fontWeight: 600 }}>{provider}</div>
                </div>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Model</span>
                    <div style={{ fontWeight: 600 }}>{model}</div>
                </div>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Total Strings</span>
                    <div style={{ fontWeight: 600 }}>{grandTotalStrings.toLocaleString()}</div>
                </div>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Total Estimated Cost</span>
                    <div style={{ fontWeight: 600, color: "var(--accent-primary)" }}>~${grandTotalCost.toFixed(4)}</div>
                </div>
            </div>

            <div
                style={{
                    flex: 1,
                    overflow: "auto",
                    background: "rgba(0,0,0,0.3)",
                    borderRadius: "8px",
                    border: "1px solid var(--glass-border)",
                    marginBottom: "1rem",
                }}
            >
                {results.map((mod) => {
                    const modCost = Object.values(mod.estimates).reduce((s, e) => s + e.estimated_cost_usd, 0)
                    return (
                        <div
                            key={mod.mod_id}
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                padding: "0.75rem 1rem",
                                borderBottom: "1px solid var(--glass-border)",
                            }}
                        >
                            <div>
                                <div style={{ fontWeight: 500 }}>{mod.mod_name}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>{mod.total_strings.toLocaleString()} strings</div>
                            </div>
                            <div style={{ fontWeight: 600, color: "var(--accent-primary)", whiteSpace: "nowrap" }}>~${modCost.toFixed(4)}</div>
                        </div>
                    )
                })}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button className="btn btn-outline" onClick={onClose}>
                    Close
                </button>
            </div>
        </Modal>
    )
}

export default EstimateTotalCostModal
