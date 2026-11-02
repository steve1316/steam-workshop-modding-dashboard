import { useState } from "react"
import { gameApi } from "@/lib/api"
import type { GlossaryTerm, LocString } from "@/lib/types"
import { GlossaryEditor, type GlossaryEditorTerm } from "@/components/GlossaryEditor"
import { renameNotice } from "@/components/GlossaryEditor/helpers"
import Modal from "@/components/ui/Modal"
import GlossaryReplacePreviewModal, { type ReplacePreview } from "@/games/chrono_ark/components/GlossaryReplacePreviewModal"

const CATEGORY_OPTIONS = ["custom", "characters", "skills", "buffs/debuffs", "items", "mechanics"]
const LANGUAGES = ["Chinese", "Korean", "Japanese"]

/** Props for ChronoArkGlossaryModal. */
interface ChronoArkGlossaryModalProps {
    /** The mod's glossary terms, owned by the parent. */
    glossary: Record<string, GlossaryTerm>
    modId: string
    strings: LocString[]
    /** Glossary changed, so the parent re-fetches it. */
    onChanged: () => void
    /** Replace-apply succeeded. The parent banners and refreshes. */
    onApplied: (message: string) => void
    /** An edit renamed existing translations, so the page reloads its rows. */
    onTranslationsChanged: () => void
    /** Delete-all requested. The parent opens the confirm dialog. */
    onRequestDeleteAll: () => void
    /** New edit suggestions were triggered, so the parent re-fetches them. */
    onSuggestionsChanged: () => void
    onClose: () => void
}

/**
 * Mod glossary dialog, a wrapper around the shared `GlossaryEditor` that adds the CRUD calls, per-term Apply, Apply All, Suggest Edits and Delete All.
 * @param glossary - Mod's glossary terms.
 * @param modId - Mod's Workshop id.
 * @param strings - All strings, to compute affected rows.
 * @param onChanged - Re-fetch the glossary.
 * @param onApplied - Banner and refresh after a replace-apply.
 * @param onTranslationsChanged - Reload rows after a rename.
 * @param onRequestDeleteAll - Open the confirm dialog for delete-all.
 * @param onSuggestionsChanged - Re-fetch suggestions.
 * @param onClose - Close handler.
 * @returns The dialog, with the replace-preview dialog nested inside.
 */
export default function ChronoArkGlossaryModal({
    glossary,
    modId,
    strings,
    onChanged,
    onApplied,
    onTranslationsChanged,
    onRequestDeleteAll,
    onSuggestionsChanged,
    onClose,
}: ChronoArkGlossaryModalProps) {
    const [notice, setNotice] = useState("")
    const [replacePreview, setReplacePreview] = useState<ReplacePreview | null>(null)

    const terms: GlossaryEditorTerm[] = Object.entries(glossary).map(([key, info]) => ({
        english: info.english || key,
        category: info.category || "custom",
        sourceMappings: info.source_mappings || {},
    }))

    const handleAdd = async (term: GlossaryEditorTerm) => {
        await gameApi("chrono_ark").post(`/mods/${modId}/glossary`, { english: term.english, source_mappings: term.sourceMappings, category: term.category })
        onChanged()
    }

    const handleUpdate = async (oldEnglish: string, term: GlossaryEditorTerm) => {
        // A new English is also renamed in translations whose source contains the term's old source.
        const res = await gameApi("chrono_ark").put(`/mods/${modId}/glossary/${encodeURIComponent(oldEnglish)}`, {
            english: term.english,
            source_mappings: term.sourceMappings,
            category: term.category,
        })
        const body = await res.json().catch(() => ({}))
        const replaced = typeof body?.replaced === "number" ? body.replaced : 0
        onChanged()
        if (term.english !== oldEnglish) setNotice(renameNotice(term.english, replaced))
        if (replaced > 0) onTranslationsChanged()
    }

    const handleRemove = async (english: string) => {
        await gameApi("chrono_ark").post(`/mods/${modId}/glossary/delete`, { terms: [english] })
        onChanged()
    }

    const applyTerm = (term: GlossaryEditorTerm) => {
        // Edits already rename existing translations, so Apply fills in the untranslated rows whose source contains the term.
        const sourceText = Object.values(term.sourceMappings)[0] || ""
        if (!sourceText) return
        const affected = strings.filter((s) => s.source.includes(sourceText) && !s.english).map((s) => ({ key: s.key, old_text: s.english, new_text: term.english }))
        setReplacePreview({ oldTerm: "", newTerm: term.english, sourceText, needsInput: true, affected })
    }

    const applyAll = () => {
        const affected: { key: string; old_text: string; new_text: string }[] = []
        for (const [english, info] of Object.entries(glossary)) {
            const sourceText = Object.values(info.source_mappings || {})[0] || ""
            if (!sourceText) continue
            for (const s of strings) {
                if (affected.some((a) => a.key === s.key)) continue
                if (s.source !== sourceText) continue
                if (s.english === english) continue
                affected.push({ key: s.key, old_text: s.english, new_text: english })
            }
        }
        if (affected.length === 0) onApplied("No strings need updating from glossary terms.")
        else setReplacePreview({ oldTerm: "", newTerm: "glossary terms", sourceText: "", needsInput: false, affected })
    }

    const suggestEdits = async () => {
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/glossary/suggest-edits`)
            if (res.ok) {
                const data = await res.json()
                if (data.new > 0) {
                    onSuggestionsChanged()
                    onApplied(`Found ${data.new} edit suggestion(s).`)
                } else {
                    onApplied("No edits to suggest.")
                }
            }
        } catch (err) {
            console.error("Failed to suggest edits:", err)
        }
    }

    const headerActions =
        terms.length > 0 ? (
            <>
                <button className="btn btn-outline btn-xs" onClick={suggestEdits}>
                    Suggest Edits
                </button>
                <button className="btn btn-outline btn-xs tone-accent" onClick={applyAll}>
                    Apply All
                </button>
                <button className="btn btn-outline btn-xs tone-danger" onClick={onRequestDeleteAll}>
                    Delete All
                </button>
            </>
        ) : undefined

    return (
        <Modal title="Mod Glossary" size="xl" fill headerActions={headerActions} onClose={onClose}>
            {notice && <p className="help-text dialog-notice">{notice}</p>}
            <GlossaryEditor
                terms={terms}
                perLanguage
                languages={LANGUAGES}
                categoryOptions={CATEGORY_OPTIONS}
                emptyMessage="No mod-specific glossary terms yet. Add terms above or accept AI suggestions."
                onAdd={handleAdd}
                onUpdate={handleUpdate}
                onRemove={handleRemove}
                fillHeight
                renderRowActions={(term) => (
                    <button className="btn btn-outline btn-xs tone-accent" onClick={() => applyTerm(term)}>
                        Apply
                    </button>
                )}
            />
            {replacePreview && <GlossaryReplacePreviewModal initialPreview={replacePreview} strings={strings} modId={modId} onClose={() => setReplacePreview(null)} onApplied={onApplied} />}
        </Modal>
    )
}
