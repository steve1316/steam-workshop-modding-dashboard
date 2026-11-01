import React, { useRef, useState } from "react"
import { FaCheck, FaTimes, FaCheckDouble, FaTimesCircle, FaPen } from "react-icons/fa"
import type { TermSuggestion } from "../../shared_types"
import { gameApi } from "../../api/games"
import Banner from "../../ui/Banner"
import Modal from "../../ui/Modal"

/** Props for {@link GlossarySuggestionModal}. */
interface GlossarySuggestionModalProps {
    /** Routes glossary API calls, e.g. "chrono_ark". */
    gameId: string
    modId: string
    suggestions: TermSuggestion[]
    onClose: () => void
    /** Fired after any accept/dismiss so the parent can refresh. */
    onUpdated: () => void
    /** When set, the modal is in batch mode. */
    batchProgress?: { current: number; total: number }
    onContinue?: () => void
    /** Subtitle shown instead of the batch progress, e.g. the Translate Names stage. */
    subtitle?: string
    /** Label for the continue button. When set, the button shows even without `batchProgress`. */
    continueLabel?: string
    /** Called after an accept with edited English renamed existing translations, so the page can reload its strings. */
    onTranslationsChanged?: () => void
}

/**
 * Modal for reviewing AI-generated glossary term suggestions. Accept or dismiss terms individually or in bulk, pruning the local list optimistically.
 *
 * @param gameId - Routes glossary API calls
 * @param modId - Mod id used in API routes
 * @param suggestions - Suggestions to review
 * @param onClose - Close handler
 * @param onUpdated - Refresh callback for the parent
 * @param batchProgress - Batch progress shown in batch mode
 * @param onContinue - Continues the run after the review
 * @param subtitle - Subtitle override
 * @param continueLabel - Continue button label override
 * @param onTranslationsChanged - Called when edited English renamed existing translations
 * @returns The suggestion review modal
 */
const GlossarySuggestionModal: React.FC<GlossarySuggestionModalProps> = ({
    gameId,
    modId,
    suggestions,
    onClose,
    onUpdated,
    batchProgress,
    onContinue,
    subtitle,
    continueLabel,
    onTranslationsChanged,
}) => {
    const isBatchMode = !!batchProgress
    const [pending, setPending] = useState<TermSuggestion[]>(suggestions)
    const [processing, setProcessing] = useState(false)
    // Edited English keyed by the suggested English. Only real changes are kept, so an entry always means "accept under this name instead".
    const [edits, setEdits] = useState<Record<string, string>>({})
    // The suggestion whose English is being typed, and the text so far.
    const [editing, setEditing] = useState<string | null>(null)
    const [draft, setDraft] = useState("")
    // Set by Enter and Escape so the blur that follows does not apply the draft a second time.
    const skipBlurRef = useRef(false)
    // What the last accept with edited English changed, shown above the list.
    const [result, setResult] = useState<string | null>(null)

    /**
     * Start editing a suggestion's English.
     *
     * @param english The suggested English.
     */
    const startEdit = (english: string) => {
        setEditing(english)
        setDraft(edits[english] ?? english)
    }

    /**
     * Keep the typed English for a suggestion. A blank or unchanged value drops the edit.
     *
     * @param english The suggested English.
     */
    const commitEdit = (english: string) => {
        const next = draft.trim()
        setEdits((prev) => {
            const rest = { ...prev }
            delete rest[english]
            return next && next !== english ? { ...rest, [english]: next } : rest
        })
        setEditing(null)
    }

    /**
     * Accept terms into the mod's glossary via POST `/api/mods/{modId}/glossary/suggestions/accept`.
     *
     * @param terms - English terms to accept
     */
    const handleAccept = async (terms: string[]) => {
        setProcessing(true)
        try {
            const renames = Object.fromEntries(terms.filter((t) => edits[t]).map((t) => [t, edits[t]]))
            const names = Object.values(renames)
            const res = await gameApi(gameId).post(`/mods/${modId}/glossary/suggestions/accept`, names.length ? { terms, renames } : { terms })
            const body = await res.json().catch(() => ({}))
            setPending((prev) => prev.filter((s) => !terms.includes(s.english)))
            if (names.length) {
                const replaced = typeof body?.replaced === "number" ? body.replaced : 0
                const count = `${replaced} translation${replaced === 1 ? "" : "s"}`
                setResult(names.length === 1 ? `${names[0]}: updated ${count}.` : `Updated ${count} to the edited names.`)
                if (replaced > 0) onTranslationsChanged?.()
            }
            onUpdated()
        } catch (err) {
            console.error("Failed to accept suggestions:", err)
        } finally {
            setProcessing(false)
        }
    }

    /**
     * Dismiss terms via POST `/api/mods/{modId}/glossary/suggestions/dismiss`. The body is `{ terms }`, or `{ all: true }` to clear every suggestion.
     *
     * @param terms - English terms to dismiss, ignored when `all` is true
     * @param all - Dismiss every pending suggestion
     */
    const handleDismiss = async (terms: string[], all: boolean = false) => {
        setProcessing(true)
        try {
            await gameApi(gameId).post(`/mods/${modId}/glossary/suggestions/dismiss`, all ? { all: true } : { terms })
            if (all) {
                setPending([])
            } else {
                setPending((prev) => prev.filter((s) => !terms.includes(s.english)))
            }
            onUpdated()
        } catch (err) {
            console.error("Failed to dismiss suggestions:", err)
        } finally {
            setProcessing(false)
        }
    }

    return (
        <Modal title="Suggested Glossary Terms" size="md" subtitle={subtitle ?? (isBatchMode ? `Batch ${batchProgress!.current} of ${batchProgress!.total}` : undefined)} onClose={onClose}>
            {result && (
                <Banner tone="success" onDismiss={() => setResult(null)}>
                    {result}
                </Banner>
            )}
            {pending.length === 0 ? (
                <p style={{ color: "var(--text-dim)", textAlign: "center", padding: "2rem" }}>No pending suggestions.</p>
            ) : (
                <>
                    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                        <button
                            className="btn btn-primary"
                            disabled={processing}
                            onClick={() => handleAccept(pending.map((s) => s.english))}
                            style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
                        >
                            <FaCheckDouble /> Accept All ({pending.length})
                        </button>
                        <button
                            className="btn btn-outline"
                            disabled={processing}
                            onClick={() => handleDismiss([], true)}
                            style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#ff4444", borderColor: "rgba(255,68,68,0.3)" }}
                        >
                            <FaTimesCircle /> Dismiss All
                        </button>
                    </div>

                    {pending.map((suggestion) => (
                        <div key={suggestion.english} style={{ padding: "1rem", marginBottom: "0.75rem", background: "rgba(0,0,0,0.2)", borderRadius: "8px", border: "1px solid var(--glass-border)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                {/* flex:1 + minWidth:0 lets long text wrap instead of pushing the buttons off-screen. */}
                                <div data-testid="suggestion-details" style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>
                                    <div className="suggestion-term">
                                        {editing === suggestion.english ? (
                                            <input
                                                className="input suggestion-term-input"
                                                aria-label={`English for ${suggestion.source}`}
                                                value={draft}
                                                autoFocus
                                                onChange={(e) => setDraft(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter") {
                                                        skipBlurRef.current = true
                                                        commitEdit(suggestion.english)
                                                    } else if (e.key === "Escape") {
                                                        // Keep Escape from also closing the dialog.
                                                        e.stopPropagation()
                                                        skipBlurRef.current = true
                                                        setEditing(null)
                                                    }
                                                }}
                                                onBlur={() => {
                                                    if (skipBlurRef.current) skipBlurRef.current = false
                                                    else commitEdit(suggestion.english)
                                                }}
                                            />
                                        ) : (
                                            <>
                                                {suggestion.edit_of && (
                                                    <>
                                                        <span style={{ textDecoration: "line-through", color: "var(--text-dim)" }}>{suggestion.edit_of}</span>
                                                        <span style={{ margin: "0 0.5rem", color: "var(--text-dim)" }}>&rarr;</span>
                                                    </>
                                                )}
                                                <span>{edits[suggestion.english] ?? suggestion.english}</span>
                                                <button
                                                    type="button"
                                                    className="icon-action suggestion-edit"
                                                    aria-label={`Edit ${edits[suggestion.english] ?? suggestion.english}`}
                                                    title="Edit the English before accepting. Accepting also renames it in translations of this source text."
                                                    disabled={processing}
                                                    onClick={() => startEdit(suggestion.english)}
                                                >
                                                    <FaPen />
                                                </button>
                                            </>
                                        )}
                                    </div>
                                    {edits[suggestion.english] && editing !== suggestion.english && (
                                        <div className="suggestion-was" data-testid="suggestion-was">
                                            was <em>{suggestion.english}</em>
                                        </div>
                                    )}
                                    <div style={{ color: "var(--text-dim)", marginTop: "0.25rem" }}>
                                        {suggestion.source_lang}: {suggestion.source}
                                    </div>
                                    <div style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginTop: "0.25rem", fontStyle: "italic" }}>{suggestion.reason}</div>
                                    <span
                                        style={{
                                            display: "inline-block",
                                            marginTop: "0.5rem",
                                            padding: "0.15rem 0.5rem",
                                            borderRadius: "4px",
                                            fontSize: "0.75rem",
                                            textTransform: "capitalize",
                                            background: "rgba(138,180,248,0.15)",
                                            color: "var(--accent-primary)",
                                        }}
                                    >
                                        {suggestion.category}
                                    </span>
                                </div>
                                <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                                    <button
                                        className="btn btn-primary"
                                        disabled={processing}
                                        onClick={() => handleAccept([suggestion.english])}
                                        style={{ padding: "0.25rem 0.75rem", display: "flex", alignItems: "center", gap: "0.25rem" }}
                                    >
                                        <FaCheck /> Accept
                                    </button>
                                    <button
                                        className="btn btn-outline"
                                        disabled={processing}
                                        onClick={() => handleDismiss([suggestion.english])}
                                        style={{ padding: "0.25rem 0.75rem", display: "flex", alignItems: "center", gap: "0.25rem" }}
                                    >
                                        <FaTimes /> Dismiss
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </>
            )}

            {(isBatchMode || continueLabel) && onContinue && (
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--glass-border)" }}>
                    <button className="btn btn-primary" disabled={processing} onClick={onContinue} style={{ padding: "0.5rem 1.5rem", fontSize: "1rem" }}>
                        {continueLabel ?? (batchProgress!.current >= batchProgress!.total ? "Finish" : pending.length === 0 ? "Continue to Next Batch" : "Skip & Continue to Next Batch")}
                    </button>
                </div>
            )}
        </Modal>
    )
}

export default GlossarySuggestionModal
