import React, { useState } from "react"
import Modal from "@/components/ui/Modal"

/** Preview data for one target language: the prompts that will be sent to the provider. */
interface LanguagePreview {
    /** Sets up the translation context and rules. */
    system_prompt: string
    /** One message per batch. */
    user_messages: string[]
    strings_in_language: number
    batches: number
}

/** Token and cost estimates for one target language, from the backend's preview/dry-run endpoint. */
interface CostEstimate {
    /** Across all batches. */
    estimated_input_tokens: number
    /** Across all batches. */
    estimated_output_tokens: number
    /** In USD, summed over all batches. */
    estimated_cost_usd: number
    /** e.g. `"gpt-4.1"`, `"claude-sonnet-5"`. */
    model: string
    /** e.g. `"Prices are approximate"`. */
    note: string
}

/** Translation preview payload returned by the backend before the user confirms the job. */
export interface TranslationPreview {
    total_strings: number
    total_batches: number
    batch_size: number
    /** e.g. `"OpenAI"`, `"Anthropic"`, `"DeepL"`. */
    provider: string
    /** Keyed by language code. */
    previews: Record<string, LanguagePreview>
    /** Keyed by language code. Absent when the provider does not support cost estimation. */
    estimates?: Record<string, CostEstimate>
}

/** Props for {@link TranslationConfirmModal}. */
interface TranslationConfirmModalProps {
    preview: TranslationPreview
    onConfirm: () => void
    onCancel: () => void
    title?: string
}

/**
 * Confirmation modal shown before a translation job, with summary stats and tabbed previews of the prompts sent to the LLM.
 * Language tabs (`activeLang`) show only for multiple languages, and prompt tabs (`activeTab`) toggle system prompt and user message.
 *
 * @param preview - Translation preview payload
 * @param onConfirm - Fires on "Translate N strings"
 * @param onCancel - Fires on Cancel or backdrop click
 * @returns The confirmation modal
 */
const TranslationConfirmModal: React.FC<TranslationConfirmModalProps> = ({ preview, onConfirm, onCancel, title }) => {
    const languages = Object.keys(preview.previews)
    const [activeLang, setActiveLang] = useState(languages[0] || "")
    const [activeTab, setActiveTab] = useState<"system" | "user">("system")
    const [activeBatch, setActiveBatch] = useState(0)
    const langPreview = preview.previews[activeLang]

    /** Sum of each language's cost, or null when the provider gives no estimates (e.g. `DeepL`), which hides the cost section. */
    const totalCost = preview.estimates ? Object.values(preview.estimates).reduce((sum, est) => sum + est.estimated_cost_usd, 0) : null
    const totalInputTokens = preview.estimates ? Object.values(preview.estimates).reduce((sum, est) => sum + est.estimated_input_tokens, 0) : null

    return (
        <Modal
            title={title || "Confirm Translation"}
            size="lg"
            fill
            onClose={onCancel}
            footer={
                <>
                    <button className="btn btn-outline" onClick={onCancel}>
                        Cancel
                    </button>
                    <button className="btn btn-primary" onClick={onConfirm}>
                        Translate {preview.total_strings} strings
                    </button>
                </>
            }
        >
            <div style={{ display: "flex", gap: "1.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Provider</span>
                    <div style={{ fontWeight: 600 }}>{preview.provider}</div>
                </div>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Strings</span>
                    <div style={{ fontWeight: 600 }}>{preview.total_strings}</div>
                </div>
                <div>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Batches</span>
                    <div style={{ fontWeight: 600 }}>
                        {preview.total_batches} (size {preview.batch_size})
                    </div>
                </div>
                {totalInputTokens !== null && (
                    <div>
                        <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Input Tokens</span>
                        <div style={{ fontWeight: 600 }}>{totalInputTokens.toLocaleString()}</div>
                    </div>
                )}
                {totalCost !== null && (
                    <div>
                        <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>Estimated Cost</span>
                        <div style={{ fontWeight: 600, color: "var(--accent-primary)" }}>
                            ~${totalCost.toFixed(4)}
                            {Object.keys(preview.estimates!).length > 1 && (
                                <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", fontWeight: 400, marginLeft: "0.5rem" }}>
                                    (
                                    {Object.entries(preview.estimates!)
                                        .map(([lang, est]) => `${lang}: ~$${est.estimated_cost_usd.toFixed(4)}`)
                                        .join(", ")}
                                    )
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {languages.length > 1 && (
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                    {languages.map((lang) => (
                        <button
                            key={lang}
                            className={`btn ${activeLang === lang ? "btn-primary" : "btn-outline"}`}
                            onClick={() => {
                                setActiveLang(lang)
                                setActiveBatch(0)
                            }}
                            style={{ padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}
                        >
                            {lang} ({preview.previews[lang].strings_in_language})
                        </button>
                    ))}
                </div>
            )}

            {langPreview && (
                <>
                    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", alignItems: "center" }}>
                        <button
                            className={`btn ${activeTab === "system" ? "btn-primary" : "btn-outline"}`}
                            onClick={() => setActiveTab("system")}
                            style={{ padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}
                        >
                            System Prompt
                        </button>
                        <button
                            className={`btn ${activeTab === "user" ? "btn-primary" : "btn-outline"}`}
                            onClick={() => setActiveTab("user")}
                            style={{ padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}
                        >
                            User Message
                        </button>
                        {activeTab === "user" && langPreview.batches > 1 && (
                            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", marginLeft: "0.5rem" }}>
                                <button
                                    className="btn btn-outline"
                                    onClick={() => setActiveBatch((b) => Math.max(0, b - 1))}
                                    disabled={activeBatch === 0}
                                    style={{ padding: "0.15rem 0.5rem", fontSize: "0.85rem", lineHeight: 1 }}
                                >
                                    &larr;
                                </button>
                                <span style={{ fontSize: "0.85rem", color: "var(--text-dim)" }}>
                                    Batch {activeBatch + 1} of {langPreview.batches}
                                </span>
                                <button
                                    className="btn btn-outline"
                                    onClick={() => setActiveBatch((b) => Math.min(langPreview.batches - 1, b + 1))}
                                    disabled={activeBatch === langPreview.batches - 1}
                                    style={{ padding: "0.15rem 0.5rem", fontSize: "0.85rem", lineHeight: 1 }}
                                >
                                    &rarr;
                                </button>
                            </div>
                        )}
                    </div>

                    <div
                        style={{
                            flex: 1,
                            overflow: "auto",
                            background: "rgba(0,0,0,0.3)",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                            padding: "1rem",
                            marginBottom: "1rem",
                            minHeight: "300px",
                        }}
                    >
                        <pre
                            style={{
                                margin: 0,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                                fontSize: "0.85rem",
                                lineHeight: "1.6",
                                color: "var(--text-main)",
                                fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace",
                            }}
                        >
                            {activeTab === "system" ? langPreview.system_prompt : langPreview.user_messages[activeBatch]}
                        </pre>
                    </div>
                </>
            )}
        </Modal>
    )
}

export default TranslationConfirmModal
