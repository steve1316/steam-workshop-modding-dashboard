/** Chrono Ark API response shapes. Keep in sync with the Pydantic models in `backend/models/api.py`. */

/** Summary status for a single mod in the dashboard listing. */
export type ModStatus = {
    /** Derived from the mod's folder name. */
    id: string
    name: string
    author: string
    has_csv: boolean
    has_dll: boolean
    total: number
    /** User-translated plus untouched. */
    translated: number
    untranslated: number
    user_translated: number
    /** Strings that already had English in the raw mod files. */
    untouched: number
    /** 0-100. */
    percentage: number
    /** ISO timestamp. */
    last_updated: string
    url?: string
    preview_image?: string | null
    /** Pending translation changes not yet synced to CSV files. */
    has_changes: boolean
}

/** A single localizable string extracted from a mod's data files, with its source text and English translation state. */
export type LocString = {
    /** Unique within the mod, e.g. "Skill/FireBolt_Name". */
    key: string
    /** e.g. "Character", "Skill", "Buff". */
    type: string
    /** Descriptor column from the CSV. */
    desc: string
    source: string
    /** e.g. "Korean", "Chinese". Null if undetectable. */
    source_lang: string | null
    /** Empty if not yet translated. */
    english: string
    is_translated: boolean
    /** English from the mod files before any user edits, used for diffing. */
    original_english: string
    /** Exported to the mod's CSV files. */
    is_synced: boolean
    /** Already had English in the raw mod files and is unmodified. */
    is_untouched: boolean
    /** English at the time of sync, used to restore synced status if the user re-enters it. */
    synced_english: string
    /** CSV/JSON/DLL file this string came from. */
    source_file: string
    /** e.g. "claude", "ollama", "manual". Empty if unknown. */
    translated_by: string
    /** If non-empty, the string cannot be translated via CSV and this says why. */
    untranslatable_reason: string
}

/** Aggregated translation statistics across all mods, shown on the Statistics page. */
export type Stats = {
    tm_entries: number
    /** Cumulative translation memory matches applied. */
    tm_hits: number
    total_mods: number
    /** 0-100. */
    global_progress: number
    total_strings: number
}

/** Full detail payload for a single mod, returned when the user opens it for editing. */
export type ModDetail = {
    id: string
    name: string
    author: string
    url: string | null
    preview_image: string | null
    strings: LocString[]
}
