import { Fragment, useMemo, useState, type ReactNode } from "react"

import HighlightText from "@/ui/HighlightText"
import SearchInput from "@/ui/SearchInput"

/** One glossary term in the shared editor's normalized shape. */
export interface GlossaryEditorTerm {
    english: string
    category: string
    /** Language -> source text. Single-source games use one entry (under any key); per-language games key by language name. */
    sourceMappings: Record<string, string>
}

/** Props for the shared `GlossaryEditor` body. */
interface GlossaryEditorProps {
    /** Heading above the list. Omit when the container already has a title. */
    title?: string
    terms: GlossaryEditorTerm[]
    /** Show a language dropdown and every `lang: text` mapping instead of a single source field. */
    perLanguage?: boolean
    /** Language options for the dropdown when `perLanguage`. */
    languages?: string[]
    /** Category dropdown options. Omit for a free-text input. */
    categoryOptions?: string[]
    /** Group rows under category headers instead of a flat list sorted by English. */
    groupByCategory?: boolean
    emptyMessage?: string
    onAdd: (term: GlossaryEditorTerm) => void | Promise<void>
    /** Update a term (the first arg is the old English key, which may be renamed). */
    onUpdate: (oldEnglish: string, term: GlossaryEditorTerm) => void | Promise<void>
    onRemove: (english: string) => void | Promise<void>
    /** Extra per-row actions next to Edit/Remove (e.g. "Apply"). */
    renderRowActions?: (term: GlossaryEditorTerm) => ReactNode
    /** Header actions next to the title (e.g. Apply All). */
    headerActions?: ReactNode
    /** Footer content below the list. */
    footer?: ReactNode
    /** Fill the container's height with the list scrolling inside it. Otherwise the list is capped at 300px. */
    fillHeight?: boolean
}

const INPUT_STYLE = { padding: "0.5rem", borderRadius: "6px", background: "rgba(0,0,0,0.2)", border: "1px solid var(--glass-border)", color: "var(--text-main)", flex: 1, minWidth: "120px" }

/** Read the single source value from a term's mappings (for non-per-language games). */
function singleSource(t: GlossaryEditorTerm): string {
    return Object.values(t.sourceMappings)[0] ?? ""
}

/**
 * Render a term's source mappings with the search query highlighted.
 * @param t - Term to render.
 * @param perLanguage - Prefix each mapping with its language.
 * @param query - Query to highlight.
 * @returns The summary.
 */
function sourceSummary(t: GlossaryEditorTerm, perLanguage: boolean, query: string): ReactNode {
    if (!perLanguage) return <HighlightText text={singleSource(t)} query={query} />
    return Object.entries(t.sourceMappings).map(([lang, text], i) => (
        <Fragment key={lang}>
            {i > 0 && ", "}
            {lang}: <HighlightText text={text} query={query} />
        </Fragment>
    ))
}

/**
 * Check whether a term matches by English text, any source text, or category.
 * @param t - Term to check.
 * @param query - Lowercased, trimmed query.
 * @returns True when it matches or the query is empty.
 */
function matchesSearch(t: GlossaryEditorTerm, query: string): boolean {
    if (!query) return true
    return t.english.toLowerCase().includes(query) || t.category.toLowerCase().includes(query) || Object.values(t.sourceMappings).some((v) => v.toLowerCase().includes(query))
}

/**
 * Shared glossary editor body: an add form, a term list with inline edit and remove, and slots for game-specific actions.
 * @param props - See `GlossaryEditorProps`.
 * @returns The editor.
 */
export function GlossaryEditor({
    title,
    terms,
    perLanguage = false,
    languages = ["Chinese", "Korean", "Japanese"],
    categoryOptions,
    groupByCategory = false,
    emptyMessage = "No glossary terms yet.",
    onAdd,
    onUpdate,
    onRemove,
    renderRowActions,
    headerActions,
    footer,
    fillHeight = false,
}: GlossaryEditorProps) {
    const defaultCategory = categoryOptions?.[0] ?? ""
    const [newEnglish, setNewEnglish] = useState("")
    const [newSource, setNewSource] = useState("")
    const [newLang, setNewLang] = useState(languages[0] ?? "Chinese")
    const [newCategory, setNewCategory] = useState(defaultCategory)
    const [editing, setEditing] = useState<string | null>(null)
    const [editEnglish, setEditEnglish] = useState("")
    const [editSource, setEditSource] = useState("")
    const [editLang, setEditLang] = useState(languages[0] ?? "Chinese")
    const [editCategory, setEditCategory] = useState(defaultCategory)
    const [search, setSearch] = useState("")

    const sorted = useMemo(() => {
        const q = search.trim().toLowerCase()
        return terms.filter((t) => matchesSearch(t, q)).sort((a, b) => a.english.localeCompare(b.english))
    }, [terms, search])
    const groups = useMemo(() => {
        if (!groupByCategory) return null
        const out = new Map<string, GlossaryEditorTerm[]>()
        for (const t of sorted) {
            const arr = out.get(t.category) ?? []
            arr.push(t)
            out.set(t.category, arr)
        }
        return [...out.entries()]
    }, [sorted, groupByCategory])

    const buildTerm = (english: string, source: string, lang: string, category: string): GlossaryEditorTerm => ({
        english,
        category,
        sourceMappings: perLanguage ? { [lang]: source } : { source },
    })

    const submitAdd = async () => {
        if (!newEnglish.trim()) return
        await onAdd(buildTerm(newEnglish, newSource, newLang, newCategory))
        setNewEnglish("")
        setNewSource("")
        setNewCategory(defaultCategory)
    }

    const startEdit = (t: GlossaryEditorTerm) => {
        setEditing(t.english)
        setEditEnglish(t.english)
        const firstLang = Object.keys(t.sourceMappings)[0] ?? languages[0] ?? "Chinese"
        setEditSource(perLanguage ? (t.sourceMappings[firstLang] ?? "") : singleSource(t))
        setEditLang(perLanguage ? firstLang : (languages[0] ?? "Chinese"))
        setEditCategory(t.category)
    }

    const submitEdit = async (oldEnglish: string) => {
        await onUpdate(oldEnglish, buildTerm(editEnglish, editSource, editLang, editCategory))
        setEditing(null)
    }

    const categoryField = (value: string, onChange: (v: string) => void) =>
        categoryOptions ? (
            <select value={value} onChange={(e) => onChange(e.target.value)} style={{ ...INPUT_STYLE, flex: "0 0 auto", minWidth: "auto" }}>
                {categoryOptions.map((c) => (
                    <option key={c} value={c}>
                        {c}
                    </option>
                ))}
            </select>
        ) : (
            <input type="text" placeholder="Category" value={value} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE} />
        )

    const renderRow = (t: GlossaryEditorTerm) => (
        <div
            key={t.english}
            className="glossary-row"
            style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap", padding: "0.5rem 0", borderBottom: "1px solid var(--glass-border)" }}
        >
            {editing === t.english ? (
                <>
                    <input type="text" value={editEnglish} onChange={(e) => setEditEnglish(e.target.value)} style={INPUT_STYLE} />
                    <input type="text" placeholder="Source" value={editSource} onChange={(e) => setEditSource(e.target.value)} style={INPUT_STYLE} />
                    {perLanguage && (
                        <select value={editLang} onChange={(e) => setEditLang(e.target.value)} style={{ ...INPUT_STYLE, flex: "0 0 auto", minWidth: "auto" }}>
                            {languages.map((l) => (
                                <option key={l} value={l}>
                                    {l}
                                </option>
                            ))}
                        </select>
                    )}
                    {categoryField(editCategory, setEditCategory)}
                    <button type="button" className="btn btn-primary" style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }} onClick={() => submitEdit(t.english)}>
                        Save
                    </button>
                    <button type="button" className="btn btn-outline" style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }} onClick={() => setEditing(null)}>
                        Cancel
                    </button>
                </>
            ) : (
                <>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ fontWeight: 500 }} className="glossary-english">
                            <HighlightText text={t.english} query={search} />
                        </span>
                        <span style={{ color: "var(--text-dim)", marginLeft: "0.75rem", fontSize: "0.85rem" }} className="glossary-source">
                            {sourceSummary(t, perLanguage, search)}
                        </span>
                        {!groupByCategory && t.category && (
                            <span
                                style={{
                                    marginLeft: "0.75rem",
                                    fontSize: "0.75rem",
                                    padding: "0.1rem 0.4rem",
                                    borderRadius: "4px",
                                    background: "rgba(138,180,248,0.15)",
                                    color: "var(--accent-primary)",
                                    textTransform: "capitalize",
                                }}
                            >
                                <HighlightText text={t.category} query={search} />
                            </span>
                        )}
                    </div>
                    <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
                        <button type="button" className="btn btn-outline btn-xs" onClick={() => startEdit(t)}>
                            Edit
                        </button>
                        {renderRowActions?.(t)}
                        <button type="button" className="btn btn-outline btn-xs tone-danger" onClick={() => onRemove(t.english)}>
                            Remove
                        </button>
                    </div>
                </>
            )}
        </div>
    )

    return (
        <div className={fillHeight ? "glossary-editor glossary-editor-fill" : "glossary-editor"}>
            {(title || headerActions) && (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    {title ? <h3 style={{ margin: 0 }}>{title}</h3> : <span />}
                    {headerActions && <div style={{ display: "flex", gap: "0.5rem" }}>{headerActions}</div>}
                </div>
            )}

            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                <input type="text" placeholder="English term" value={newEnglish} onChange={(e) => setNewEnglish(e.target.value)} style={INPUT_STYLE} />
                <input type="text" placeholder="Source text" value={newSource} onChange={(e) => setNewSource(e.target.value)} style={INPUT_STYLE} />
                {perLanguage && (
                    <select value={newLang} onChange={(e) => setNewLang(e.target.value)} style={{ ...INPUT_STYLE, flex: "0 0 auto", minWidth: "auto" }}>
                        {languages.map((l) => (
                            <option key={l} value={l}>
                                {l}
                            </option>
                        ))}
                    </select>
                )}
                {categoryField(newCategory, setNewCategory)}
                <button type="button" className="btn btn-primary" disabled={!newEnglish.trim()} onClick={submitAdd}>
                    Add
                </button>
            </div>

            {terms.length > 0 && (
                <div style={{ marginBottom: "0.75rem" }}>
                    <SearchInput value={search} onChange={setSearch} placeholder="Search terms..." />
                </div>
            )}

            {terms.length === 0 ? (
                <p style={{ color: "var(--text-dim)", textAlign: "center" }}>{emptyMessage}</p>
            ) : sorted.length === 0 ? (
                <p style={{ color: "var(--text-dim)", textAlign: "center" }}>No terms match "{search.trim()}".</p>
            ) : groups ? (
                <div className="glossary-editor-list">
                    {groups.map(([cat, items]) => (
                        <div key={cat}>
                            <div className="glossary-group-header" style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--text-dim)", marginTop: "0.5rem" }}>
                                <HighlightText text={cat || "uncategorized"} query={search} />
                            </div>
                            {items.map(renderRow)}
                        </div>
                    ))}
                </div>
            ) : (
                <div className="glossary-editor-list">{sorted.map(renderRow)}</div>
            )}

            {footer}
        </div>
    )
}
