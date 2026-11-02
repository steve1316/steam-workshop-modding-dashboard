import { useEffect, useRef, useState } from "react"
import type { KeyboardEvent } from "react"
import type { GlossaryTerm } from "@/lib/types"
import type { LocString } from "@/games/chrono_ark/lib/types"
import Modal from "@/components/ui/Modal"
import { findGlossaryMatches, findPairedRow } from "@/games/chrono_ark/components/ManualTranslateModal/matching"

/** Props for ManualTranslateModal. */
interface ManualTranslateModalProps {
    /** Rows to step through, in order. Snapshotted on open so saving a row does not shift the queue. */
    queue: LocString[]
    /** Every row of the mod, used to find a row's paired Name or Description. */
    allStrings: LocString[]
    /** The mod glossary, keyed by English term. */
    glossary: Record<string, GlossaryTerm>
    /** The mod's source language, used to pick each term's source text. */
    sourceLanguage: string
    /** Language the rows are translated into, shown as the input label. */
    targetLanguage: string
    /** Persists one row. Resolves to false when the save failed. */
    onSave: (key: string, english: string) => Promise<boolean>
    onClose: () => void
}

/**
 * Steps through rows one at a time so they can be translated by hand, saving each through the normal row-edit path.
 *
 * @param queue Rows to step through.
 * @param allStrings Every row of the mod.
 * @param glossary The mod glossary.
 * @param sourceLanguage The mod's source language.
 * @param targetLanguage Language the rows are translated into.
 * @param onSave Persists one row.
 * @param onClose Close handler.
 * @returns The dialog.
 */
export default function ManualTranslateModal({ queue, allStrings, glossary, sourceLanguage, targetLanguage, onSave, onClose }: ManualTranslateModalProps) {
    const [rows] = useState(queue)
    const [index, setIndex] = useState(0)
    const [value, setValue] = useState(queue[0]?.english ?? "")
    const [savedCount, setSavedCount] = useState(0)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState("")
    const inputRef = useRef<HTMLTextAreaElement>(null)

    const done = index >= rows.length
    const row = rows[index]
    const paired = row ? findPairedRow(row.key, allStrings) : undefined
    const matches = row ? findGlossaryMatches(row.source, glossary, sourceLanguage) : []

    useEffect(() => {
        inputRef.current?.focus()
    }, [index])

    /**
     * Move to another row and load its current English.
     *
     * @param next The row index to show.
     */
    const goTo = (next: number) => {
        setIndex(next)
        setValue(rows[next]?.english ?? "")
        setError("")
    }

    const saveAndNext = async () => {
        if (!row || saving) return
        const trimmed = value.trim()
        // An unchanged row is not re-saved, so stepping past it does not stamp it as "manual".
        if (trimmed && trimmed !== row.english) {
            setSaving(true)
            const ok = await onSave(row.key, trimmed)
            setSaving(false)
            if (!ok) {
                setError("Could not save this translation. Try again.")
                return
            }
            setSavedCount((n) => n + 1)
        }
        goTo(index + 1)
    }

    const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && e.ctrlKey) {
            e.preventDefault()
            saveAndNext()
        }
    }

    const footer = done ? (
        <button type="button" className="btn btn-primary" onClick={onClose}>
            Close
        </button>
    ) : (
        <>
            <button type="button" className="btn btn-outline" onClick={() => goTo(index - 1)} disabled={index === 0 || saving}>
                Back
            </button>
            <button type="button" className="btn btn-outline" onClick={() => goTo(index + 1)} disabled={saving}>
                Skip
            </button>
            <button type="button" className="btn btn-primary" onClick={saveAndNext} disabled={saving || !value.trim()}>
                Save &amp; Next
            </button>
        </>
    )

    return (
        <Modal title="Manual Translation" subtitle={done ? `${rows.length} of ${rows.length}` : `${index + 1} of ${rows.length}`} onClose={onClose} footer={footer}>
            <div className="progress-bar manual-progress">
                <div className="progress-bar-fill" style={{ width: `${(Math.min(index, rows.length) / rows.length) * 100}%` }} />
            </div>
            {done ? (
                <p className="manual-done">
                    Saved {savedCount} of {rows.length}. They show as Pending until you run Sync Changes.
                </p>
            ) : (
                <div className="manual-body">
                    <div className="manual-key">
                        <span>{row.key}</span>
                        <span className="manual-file">{row.source_file}</span>
                    </div>
                    <div className="field">
                        <span className="field-label">Original ({sourceLanguage})</span>
                        <div className="manual-original">{row.source}</div>
                    </div>
                    {matches.length > 0 && (
                        <div className="field">
                            <span className="field-label">Glossary matches</span>
                            <div className="manual-box">
                                {matches.map((m) => (
                                    <div key={m.source} className="manual-term">
                                        <span>{m.source}</span>
                                        <span className="manual-arrow">&rarr;</span>
                                        <strong>{m.english}</strong>
                                        {m.source === row.source.trim() && (
                                            <button
                                                type="button"
                                                className="btn btn-outline btn-sm"
                                                onClick={() => {
                                                    setValue(m.english)
                                                    inputRef.current?.focus()
                                                }}
                                            >
                                                Use
                                            </button>
                                        )}
                                        <span className="manual-category">{m.category}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    {paired && (
                        <div className="field">
                            <span className="field-label">Paired {/_name$/i.test(paired.key) ? "name" : "description"}</span>
                            <div className="manual-box">
                                <div>{paired.source}</div>
                                {paired.english && <div className="manual-paired-english">{paired.english}</div>}
                            </div>
                        </div>
                    )}
                    <div className="field">
                        <label className="field-label" htmlFor="manual-english">
                            {targetLanguage}
                        </label>
                        <textarea
                            id="manual-english"
                            ref={inputRef}
                            className="textarea manual-input"
                            value={value}
                            placeholder={`Type the ${targetLanguage} translation...`}
                            onChange={(e) => setValue(e.target.value)}
                            onKeyDown={onKeyDown}
                        />
                    </div>
                    {error && <p className="dialog-error">{error}</p>}
                    <p className="manual-hint">Ctrl+Enter saves and moves on. Esc closes. Saved rows are marked "manual".</p>
                </div>
            )}
        </Modal>
    )
}
