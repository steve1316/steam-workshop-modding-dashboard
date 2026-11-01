import type { ModStatus } from "../shared_types"

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
