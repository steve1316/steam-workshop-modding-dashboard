import { useMemo, useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import type { Glossary, GlossaryTerm } from "@/lib/types"
import ErrorState from "@/components/ui/ErrorState"
import LoadingState from "@/components/ui/LoadingState"
import PageHeader from "@/components/ui/PageHeader"
import Panel from "@/components/ui/Panel"
import SearchInput from "@/components/ui/SearchInput"
import { extractCategories, filterGlossaryTerms } from "@/lib/search"

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
    /** Keys the cached glossary, so each game's stays separate. */
    gameId: string
    /** Called on open and on Retry. */
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
 * @param gameId Game the glossary belongs to.
 * @param load Glossary loader.
 * @param englishWidth English Term column width.
 * @param categoryWidth Category column width.
 * @param columns Game-specific columns.
 * @returns The glossary page.
 */
export default function GlossaryBrowser({ gameId, load, englishWidth, categoryWidth, columns }: GlossaryBrowserProps) {
    const { data: glossary, error, isFetching, refetch } = useQuery({ queryKey: [gameId, "base-glossary"], queryFn: load })
    const [search, setSearch] = useState("")
    const [categoryFilter, setCategoryFilter] = useState("all")

    const terms = useMemo(() => glossary?.terms ?? {}, [glossary])
    const categories = useMemo(() => extractCategories(terms), [terms])
    const filteredTerms = useMemo(() => filterGlossaryTerms(terms, search, categoryFilter), [terms, search, categoryFilter])

    // While Retry is in flight the loading state shows instead of the old error.
    if (error && !isFetching)
        return <ErrorState title="Could not load the glossary" message={`${error.message}. Check that the backend is running, then retry.`} action={{ label: "Retry", onClick: () => refetch() }} />
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
