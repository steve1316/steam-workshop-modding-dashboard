/** Filter and sort helpers for the Chrono Ark mod grid and strings table. */

import type { ModStatus, LocString } from "@/games/chrono_ark/lib/types"
import { matchesSearch } from "@/lib/search"
import type { RowStatus } from "@/lib/types"

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
 * Filter mods by a case-insensitive search across name and author. Blank search returns all mods.
 * @param mods - Mods to filter.
 * @param search - Search query.
 * @returns Matching mods.
 */
export function filterMods(mods: ModStatus[], search: string): ModStatus[] {
    return mods.filter((mod) => matchesSearch(search, mod.name, mod.author))
}
