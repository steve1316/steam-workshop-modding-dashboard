/** Shared types mirroring the backend API response shapes. Keep in sync with the Pydantic models in `backend/models/api.py`. */

import type { RowStatus } from "@/lib/stringFilters"

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

/** A glossary term mapping a canonical English term to its source-language equivalents. */
export type GlossaryTerm = {
    english?: string
    /** e.g. "characters", "skills", "mechanics", "custom". */
    category: string
    /** Localization key that defined this term. Empty for manual entries. */
    key: string
    /** CSV the term came from. Empty for manual/seed entries. */
    source_file?: string
    /** Source language name to native text, e.g. { "Korean": "hwayeomgu" }. */
    source_mappings: Record<string, string>
    /** ISO timestamp. */
    created_at?: string
    /** ISO timestamp. */
    updated_at?: string
}

/** The complete glossary for a mod or the global glossary. */
export type Glossary = {
    /** Keyed by English term. */
    terms: Record<string, GlossaryTerm>
}

/** An AI-generated glossary term suggestion from the backend. */
export type TermSuggestion = {
    english: string
    source: string
    /** e.g. "Korean". */
    source_lang: string
    category: string
    reason: string
    /** For edit suggestions, the original term being replaced. */
    edit_of?: string
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

// //////////////////////////////////////////////////////////////////////////////////////////////////
// //////////////////////////////////////////////////////////////////////////////////////////////////
// Total War: Warhammer III - translation mod types (see `backend/games/total_war_warhammer_3/routes/translation.py`)

/** Summary row returned by `GET /api/games/total_war_warhammer_3/translation/mods`. */
export interface WH3TranslationModSummary {
    /** Steam Workshop ID of the translation mod. */
    workshop_id: string
    display_name: string
    /** Workshop IDs of the parent mods this translation covers. */
    parent_workshop_ids: string[]
    /** Absolute path to the local `.loc.tsv` source folder. */
    local_source_dir: string
    /** e.g. `"Chinese"`. */
    source_language: string
    /** e.g. `"English"`. */
    target_language: string
    /** Relative URL of the parent mod's preview `.png`. `null` when unreachable. */
    preview_image_url: string | null
}

/** Status of one row in the drift report. */
export type WH3DriftStatus = "translated" | "untranslated" | "stale" | "orphan"

/** One row in `GET /translation/mods/{id}/strings`. */
export interface WH3DriftRow {
    /** Normalized parent `.loc.tsv` filename. */
    source_filename: string
    key: string
    /** `null` only when `status === "orphan"`. */
    parent_text: string | null
    /** `null` only when `status === "untranslated"`. */
    translation_text: string | null
    status: WH3DriftStatus
    /** Who produced the translation. `null` when untranslated. */
    provider: string | null
    /** Six-state status for the shared status chips. `null` if the backend did not supply it. */
    canonical_status: RowStatus | null
    /** Previously-synced `.loc.tsv` text, for the strikethrough. `null` when none on disk. */
    previous_text: string | null
}

/** Summary returned by `POST /api/games/total_war_warhammer_3/translation/mods/{id}/rescan`. */
export interface WH3RescanSummary {
    mod_id: string
    counts: Record<WH3DriftStatus, number>
    /** Zero-filled tally of each row's `canonical_status`. */
    canonical_counts: Record<RowStatus, number>
    /** ISO timestamp. */
    scanned_at: string
    /** True when translations.json differs from the user's `.loc.tsv` files. */
    has_unsynced_changes: boolean
    /** True when any of `source_game`, `character_name` or `background` is non-empty. */
    has_mod_context: boolean
}

/** Body of `GET/PUT /api/games/total_war_warhammer_3/translation/mods/{id}/mod-context`. */
export interface WH3ModContext {
    /** Free-form, e.g. `"WH3"`. */
    source_game: string
    /** Free-form, e.g. `"Zerooz Cathy"`. */
    character_name: string
    /** Lore injected into the LLM prompt. */
    background: string
    /** `null` falls back to the registry default. */
    source_language_override: string | null
    /** `null` falls back to the registry default. */
    target_language_override: string | null
    /** Also send translated names not in the glossary with every prompt. Missing on older backends. */
    include_translated_names?: boolean
}

/** One row in `GET /translation/mods/{id}/glossary` response (also used in POST/PUT bodies). */
export interface WH3GlossaryEntry {
    /** Also the dict key on the wire. */
    english: string
    source: string
    /** e.g. `"factions"`. */
    category: string
}

/** One backup in a mod's history, the same shape for every game. */
export interface HistoryEntry {
    id: string
    /** Why the backup was created (e.g. "Before translation run"). */
    reason: string
    /** "auto" for backups taken before destructive ops, "manual" for user saves. */
    kind?: "auto" | "manual"
    /** ISO timestamp. */
    created_at: string
    files: string[]
    /** Translated string count at backup time, when recorded. */
    translated_count?: number
    /** Total translatable string count at backup time, when recorded. */
    total_count?: number
    /** Glossary term count at backup time, when recorded. */
    glossary_count?: number
}

/** One entry in a mod's `api-responses` log, the same shape for every game. */
export interface ApiLogEntry {
    /** ISO timestamp. */
    timestamp: string
    kind: "translate-batch" | "scan-terms" | "suggest-edits"
    /** e.g. `"claude"`. */
    provider: string
    /** `"claude"` for calls that do not report one. */
    model: string
    /** `null` when the provider does not report it. */
    input_tokens: number | null
    output_tokens: number | null
    /** Estimated, in USD. */
    cost_usd: number | null
    /** Keys (translate-batch) or input strings (scan-terms / suggest-edits). */
    keys_or_inputs: string[]
    /** A failed call leads with an `ERROR:` line. */
    raw_response: string
}

/** Response body of `POST /translation/mods/{id}/sync`. */
export interface WH3SyncResult {
    /** Absolute `.loc.tsv` path to number of keys written. */
    per_file: Record<string, number>
    /** Orphan rows (translated keys with no parent source) pruned during this sync. */
    removed_orphans: number
    /** The `.pack` was rebuilt from the synced loose files. */
    pack_built: boolean
    /** Why the pack rebuild did not complete. Null when it succeeded or was not applicable. */
    pack_error: string | null
}
