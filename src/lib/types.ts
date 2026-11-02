/** Cross-game types mirroring the backend API response shapes. Keep in sync with the Pydantic models in `backend/models/api.py`. */

/** Canonical status of a translation table row, shared by every game. */
export type RowStatus = "synced" | "untouched" | "pending" | "changed" | "missing" | "untranslatable"

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
