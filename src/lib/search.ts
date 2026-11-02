/** Search and filter helpers shared by the dashboards and glossaries. */

import type { GlossaryTerm } from "@/lib/types"

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
