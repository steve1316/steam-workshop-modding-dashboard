import { useEffect, useMemo, useState, type ReactNode } from "react"

import type { Glossary, GlossaryTerm } from "../shared_types"
import ErrorState from "../ui/ErrorState"
import LoadingState from "../ui/LoadingState"
import PageHeader from "../ui/PageHeader"
import Panel from "../ui/Panel"
import SearchInput from "../ui/SearchInput"
import { extractCategories, filterGlossaryTerms } from "../utils/glossaryFilters"

/** One game-specific column of the glossary table. */
export interface GlossaryColumn {
    /** Also the React key, so it must be unique. */
    header: string
    /** Pixels. Omit to share the remaining width. */
    width?: number
    /** Classes for the cells, e.g. `cell-dim cell-mono`. */
    className?: string
    render: (termKey: string, term: GlossaryTerm) => ReactNode
}

/** Props for GlossaryBrowser. */
interface GlossaryBrowserProps {
    /** Called on open and on Retry. Must be a stable (module-level) function, since it is an effect dependency. */
    load: () => Promise<Glossary>
    /** Pixels. */
    englishWidth: number
    /** Pixels. */
    categoryWidth: number
    columns: GlossaryColumn[]
}

/**
 * Base-game glossary page shared by both games: counts, search with category pills, and a table of English Term, Category and game-specific columns.
 *
 * @param load Glossary loader.
 * @param englishWidth English Term column width.
 * @param categoryWidth Category column width.
 * @param columns Game-specific columns.
 * @returns The glossary page.
 */
export default function GlossaryBrowser({ load, englishWidth, categoryWidth, columns }: GlossaryBrowserProps) {
    const [glossary, setGlossary] = useState<Glossary | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [attempt, setAttempt] = useState(0)
    const [search, setSearch] = useState("")
    const [categoryFilter, setCategoryFilter] = useState("all")

    useEffect(() => {
        let cancelled = false
        load()
            .then((data) => {
                if (!cancelled) setGlossary(data)
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(err instanceof Error ? err.message : String(err))
            })
        return () => {
            cancelled = true
        }
    }, [load, attempt])

    const terms = useMemo(() => glossary?.terms ?? {}, [glossary])
    const categories = useMemo(() => extractCategories(terms), [terms])
    const filteredTerms = useMemo(() => filterGlossaryTerms(terms, search, categoryFilter), [terms, search, categoryFilter])

    /** Clear the error, which brings back the loading state, and load again. */
    const retry = () => {
        setError(null)
        setAttempt((n) => n + 1)
    }

    if (error) return <ErrorState title="Could not load the glossary" message={`${error}. Check that the backend is running, then retry.`} action={{ label: "Retry", onClick: retry }} />
    if (!glossary) return <LoadingState message="Loading glossary..." />

    return (
        <div className="glossary-view animate-fade-in">
            <PageHeader
                title="Terminology Glossary"
                meta={
                    <p>
                        {Object.keys(terms).length} base game terms across {categories.length} categories
                    </p>
                }
            />

            <Panel className="filter-bar">
                <div className="filter-bar-row">
                    <SearchInput value={search} onChange={setSearch} placeholder="Search terms..." />
                    <div className="filter-pills">
                        <button type="button" className={`filter-pill btn ${categoryFilter === "all" ? "btn-primary" : "btn-outline"}`} onClick={() => setCategoryFilter("all")}>
                            All
                        </button>
                        {categories.map((cat) => (
                            <button
                                key={cat}
                                type="button"
                                className={`filter-pill pill-capitalize btn ${categoryFilter === cat ? "btn-primary" : "btn-outline"}`}
                                onClick={() => setCategoryFilter(cat)}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>
                </div>
            </Panel>

            <div className="glass-card static data-table-card">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th style={{ width: englishWidth }}>English Term</th>
                            <th style={{ width: categoryWidth }}>Category</th>
                            {columns.map((col) => (
                                <th key={col.header} style={col.width ? { width: col.width } : undefined}>
                                    {col.header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {filteredTerms.map(([termKey, term]) => (
                            <tr key={termKey}>
                                <td className="term-english">{term.english || termKey}</td>
                                <td className="term-category">{term.category}</td>
                                {columns.map((col) => (
                                    <td key={col.header} className={col.className}>
                                        {col.render(termKey, term)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {filteredTerms.length === 0 && (
                            <tr>
                                <td colSpan={2 + columns.length} className="data-table-empty">
                                    No matching terms found.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
