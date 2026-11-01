import React, { useCallback, useEffect, useState } from "react"

import { GlossaryEditor, type GlossaryEditorTerm } from "../../../../translation/GlossaryEditor"
import { renameNotice } from "../../../../translation/renameNotice"
import { addGlossaryTerm, deleteAllGlossaryTerms, deleteGlossaryTerm, glossaryApplyAll, glossarySuggestEdits, loadGlossary, updateGlossaryTerm } from "../../translationApi"
import Modal from "../../../../ui/Modal"
import { useConfirm } from "../../../../ui/useConfirm"

/** Props for `ModGlossaryModal`. */
interface ModGlossaryModalProps {
    workshopId: string
    onClose: () => void
    /** Called with the saved edit-suggestion count so the page can refresh its Suggestions count. */
    onSuggestionsChanged: (added: number) => void
    /** Called after an edit or Apply All changed translations, so the page reloads its rows. */
    onTranslationsChanged?: () => void
}

/** Read the single source text from an editor term's mappings, since WH3 stores one per term. */
function sourceOf(term: GlossaryEditorTerm): string {
    return Object.values(term.sourceMappings)[0] ?? ""
}

/**
 * Per-mod glossary editor modal, a thin wrapper around the shared `GlossaryEditor` that wires CRUD, Suggest Edits, Apply All and Delete All to the WH3 API.
 *
 * @param workshopId Translation mod Workshop id.
 * @param onClose Called when the modal closes.
 * @param onSuggestionsChanged Called with the saved suggestion count.
 * @param onTranslationsChanged Called after an edit or Apply All changed translations.
 * @returns The modal.
 */
const ModGlossaryModal: React.FC<ModGlossaryModalProps> = ({ workshopId, onClose, onSuggestionsChanged, onTranslationsChanged }) => {
    const [terms, setTerms] = useState<GlossaryEditorTerm[]>([])
    const [error, setError] = useState("")
    const [notice, setNotice] = useState("")
    const [suggesting, setSuggesting] = useState(false)
    const [applyAllOpen, setApplyAllOpen] = useState(false)
    const [applyAllOld, setApplyAllOld] = useState("")
    const [applyAllNew, setApplyAllNew] = useState("")
    const [applyResult, setApplyResult] = useState("")
    const { confirm, confirmDialog } = useConfirm()

    const refresh = useCallback(async () => {
        try {
            const dict = await loadGlossary(workshopId)
            setTerms(Object.entries(dict).map(([english, v]) => ({ english, category: v.category, sourceMappings: { source: v.source } })))
        } catch (e) {
            setError((e as Error).message)
        }
    }, [workshopId])

    useEffect(() => {
        refresh()
    }, [refresh])

    const handleAdd = async (term: GlossaryEditorTerm) => {
        try {
            await addGlossaryTerm(workshopId, { english: term.english, source: sourceOf(term), category: term.category })
            await refresh()
        } catch (e) {
            setError((e as Error).message)
        }
    }

    const handleUpdate = async (oldEnglish: string, term: GlossaryEditorTerm) => {
        try {
            const { replaced } = await updateGlossaryTerm(workshopId, oldEnglish, { english: term.english, source: sourceOf(term), category: term.category })
            await refresh()
            if (term.english !== oldEnglish) setNotice(renameNotice(term.english, replaced))
            if (replaced > 0) onTranslationsChanged?.()
        } catch (e) {
            setError((e as Error).message)
        }
    }

    const handleRemove = async (english: string) => {
        const ok = await confirm({ title: "Remove glossary term", message: `Remove the glossary entry "${english}"?`, confirmLabel: "Remove", variant: "danger" })
        if (!ok) return
        try {
            await deleteGlossaryTerm(workshopId, english)
            await refresh()
        } catch (e) {
            setError((e as Error).message)
        }
    }

    const handleDeleteAll = async () => {
        const ok = await confirm({ title: "Delete All Glossary Terms", message: `Delete all ${terms.length} glossary term(s)?`, confirmLabel: "Delete All", variant: "danger" })
        if (!ok) return
        try {
            await deleteAllGlossaryTerms(workshopId)
            await refresh()
        } catch (e) {
            setError((e as Error).message)
        }
    }

    const onSuggestEdits = async () => {
        setSuggesting(true)
        setNotice("")
        try {
            const result = await glossarySuggestEdits(workshopId)
            onSuggestionsChanged(result.new)
            setNotice(result.new > 0 ? `Added ${result.new} edit suggestion(s). Review them from the Suggestions button.` : "No edits to suggest.")
        } catch (e) {
            setError((e as Error).message)
        } finally {
            setSuggesting(false)
        }
    }

    const runApplyAll = async () => {
        if (!applyAllOld.trim() || !applyAllNew.trim()) return
        try {
            const result = await glossaryApplyAll(workshopId, applyAllOld, applyAllNew)
            setApplyResult(`Replaced ${result.replaced} occurrences`)
            if (result.replaced > 0) onTranslationsChanged?.()
            setApplyAllOld("")
            setApplyAllNew("")
        } catch (e) {
            setError((e as Error).message)
        }
    }

    const headerActions = (
        <>
            <button type="button" className="btn btn-outline btn-xs" onClick={onSuggestEdits} disabled={suggesting}>
                {suggesting ? "Suggesting..." : "Suggest Edits"}
            </button>
            <button type="button" className="btn btn-outline btn-xs tone-accent" onClick={() => setApplyAllOpen(!applyAllOpen)}>
                Apply All
            </button>
            {terms.length > 0 && (
                <button type="button" className="btn btn-outline btn-xs tone-danger" onClick={handleDeleteAll}>
                    Delete All
                </button>
            )}
        </>
    )

    const footer = (
        <>
            {applyAllOpen && (
                <div className="glossary-apply-all">
                    <input type="text" placeholder="Old English" value={applyAllOld} onChange={(e) => setApplyAllOld(e.target.value)} />
                    <input type="text" placeholder="New English" value={applyAllNew} onChange={(e) => setApplyAllNew(e.target.value)} />
                    <button type="button" className="btn btn-primary" onClick={runApplyAll}>
                        Apply
                    </button>
                </div>
            )}
            {applyResult && <p style={{ color: "var(--text-dim)", margin: "0.5rem 0" }}>{applyResult}</p>}
        </>
    )

    return (
        <Modal title="Mod Glossary" size="xl" fill headerActions={headerActions} onClose={onClose}>
            {error && <p className="dialog-error">{error}</p>}
            {notice && <p className="help-text dialog-notice">{notice}</p>}
            <GlossaryEditor terms={terms} groupByCategory fillHeight emptyMessage="No glossary entries yet." onAdd={handleAdd} onUpdate={handleUpdate} onRemove={handleRemove} footer={footer} />
            {confirmDialog}
        </Modal>
    )
}

export default ModGlossaryModal
