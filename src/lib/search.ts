/** Search, filter and sort helpers for the mod grids, string tables and glossaries. */
import type { GlossaryTerm, LocString, ModStatus } from "@/lib/types"

export type RowStatus = "synced" | "untouched" | "pending" | "changed" | "missing" | "untranslatable"

export type FilterTab = "all" | "missing" | "untouched" | "pending" | "synced"

export type SortField = "is_translated" | "translated_by" | "key" | "source_file" | "source" | "english"

export type SortDirection = "asc" | "desc" | null

export type SortConfig = { key: SortField; direction: SortDirection }

/**
 * Get the display status for a string table row.
 * @param s - String to evaluate.
 * @returns Status for the badge.
 */
export function getRowStatus(s: LocString): RowStatus {
    if (s.untranslatable_reason) return "untranslatable"
    if (s.is_synced) return "synced"
    if (s.is_untouched) return "untouched"
    if (s.is_translated || !s.source.trim()) return "pending"
    return "missing"
}

/**
 * Filter strings by status tab and search. Rows with empty source text are always hidden.
 * @param strings - All strings.
 * @param filter - Active filter tab.
 * @param search - Search query.
 * @returns Matching strings.
 */
export function filterStrings(strings: LocString[], filter: FilterTab, search: string): LocString[] {
    const q = search.toLowerCase()
    return strings.filter((s) => {
        if (!s.source.trim()) return false

        const isDone = s.is_translated
        const isPending = isDone && !s.is_synced
        const isUntouched = !!s.is_untouched
        const isUntranslatable = !!s.untranslatable_reason
        const matchesFilter =
            filter === "all" ||
            (filter === "missing" && !isDone && !isUntranslatable) ||
            (filter === "untouched" && isUntouched) ||
            (filter === "pending" && isPending && !isUntouched) ||
            (filter === "synced" && s.is_synced)

        if (!matchesFilter) return false

        if (!q) return true
        return s.key.toLowerCase().includes(q) || s.source_file.toLowerCase().includes(q) || s.source.toLowerCase().includes(q) || s.english.toLowerCase().includes(q)
    })
}

/**
 * Sort strings by column and direction without mutating the input.
 * @param strings - Strings to sort.
 * @param config - Sort column and direction.
 * @returns Sorted copy, or a shallow copy if direction is null.
 */
export function sortStrings(strings: LocString[], config: SortConfig): LocString[] {
    const result = [...strings]
    if (!config.direction) return result

    result.sort((a, b) => {
        const aValue = a[config.key]
        const bValue = b[config.key]
        if (aValue === bValue) return 0
        const comparison = aValue < bValue ? -1 : 1
        return config.direction === "asc" ? comparison : -comparison
    })

    return result
}

/**
 * Check case-insensitively that any field contains the search text. Blank search matches everything.
 * @param search - Search query.
 * @param fields - Values to search, such as a name and a workshop id. Null and undefined are skipped.
 * @returns True when the item should stay visible.
 */
export function matchesSearch(search: string, ...fields: (string | null | undefined)[]): boolean {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return fields.some((field) => (field ?? "").toLowerCase().includes(query))
}

/**
 * Filter mods by a case-insensitive search across name and author. Blank search returns all mods.
 * @param mods - Mods to filter.
 * @param search - Search query.
 * @returns Matching mods.
 */
export function filterMods(mods: ModStatus[], search: string): ModStatus[] {
    return mods.filter((mod) => matchesSearch(search, mod.name, mod.author))
}

/**
 * Get the unique categories of glossary terms, sorted.
 * @param terms - English term to `GlossaryTerm`.
 * @returns Sorted categories.
 */
export function extractCategories(terms: Record<string, GlossaryTerm>): string[] {
    const cats = new Set<string>()
    for (const term of Object.values(terms)) {
        cats.add(term.category)
    }
    return Array.from(cats).sort()
}

/**
 * Filter and sort glossary terms. Search is case-insensitive over the English text, key, and source mapping values.
 * @param terms - Term key to `GlossaryTerm`.
 * @param search - Search query.
 * @param categoryFilter - Category, or "all".
 * @returns Sorted `[termKey, GlossaryTerm]` tuples.
 */
export function filterGlossaryTerms(terms: Record<string, GlossaryTerm>, search: string, categoryFilter: string): [string, GlossaryTerm][] {
    const q = search.toLowerCase()
    return Object.entries(terms)
        .filter(([termKey, info]) => {
            const english = info.english || termKey
            const matchesSearch = !q || english.toLowerCase().includes(q) || info.key.toLowerCase().includes(q) || Object.values(info.source_mappings).some((v) => v.toLowerCase().includes(q))
            const matchesCategory = categoryFilter === "all" || info.category === categoryFilter
            return matchesSearch && matchesCategory
        })
        .sort(([aKey, aInfo], [bKey, bInfo]) => (aInfo.english || aKey).localeCompare(bInfo.english || bKey))
}
