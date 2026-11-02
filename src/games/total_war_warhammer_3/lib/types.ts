/** Total War: Warhammer III API shapes for the translation, registry, runner and publish routes. */

import type { RowStatus } from "@/lib/types"

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

export interface SupportedMod {
    name: string
    package_name: string
    path: string
    modified_attributes?: string[]
    /** Derived from `path`. Null when the path does not follow the TW3 workshop convention. */
    workshop_id?: string | null
    /** Glob pattern to faction code, overriding default faction detection. */
    pattern_overrides?: Record<string, string>
    /** Lord/hero `key` to allowed lists, overriding the default character set. */
    character_overrides?: Record<string, { allowed_lords?: unknown[]; allowed_heroes?: unknown[] }>
    /** Excludes the mod from auto-generation. */
    ignore_generation?: boolean
    [key: string]: unknown
}

/** Progress of one script inside an `update` pipeline run. */
export type StepStatus = "queued" | "running" | "done" | "skipped" | "failed"

/** A run that is currently active. */
export interface RunStateRunning {
    status: "running"
    run_id: string
    script_id: string
    started_at: string
    lines_emitted: number
    /** Per-script progress of an `update` pipeline run, keyed by script id. Empty for every other run. */
    steps: Record<string, StepStatus>
}

/** State when no run is active. */
export interface RunStateIdle {
    status: "idle"
}

export type RunState = RunStateRunning | RunStateIdle

export interface ValidationIssue {
    kind: "missing_effect_category" | "missing_mod_path"
    severity: "error"
    mod_package_name: string
    mod_name: string
    /** The orphaned reference: a missing category name or path string. */
    target: string
    message: string
}

/** Handle returned by `publishPack` for the spawned SteamCMD subprocess. */
export interface PublishHandle {
    publish_id: string
    workshop_id: string
    started_at: string
}

/** One generated Workshop changenote returned by `fetchChangeNotes`. */
export interface ChangeNote {
    /** Steam BBCode. */
    note: string
    /** False means nothing changed since the last recorded upload. */
    pending: boolean
    kind: "compat" | "translation"
}

/** Response of `fetchChangeNotes`. */
export interface ChangeNotesResponse {
    /** Null when no note could be generated. */
    notes: Record<string, ChangeNote | null>
    /** Messages from failed generators. */
    errors: string[]
}

/** One mod entry sent in a batch publish request. */
export interface BatchPublishItem {
    /** Empty or non-numeric values are filtered server-side into the skipped list. */
    workshop_id: string
    /** Carried through the SSE stream for display. */
    title: string
    /** Must be non-empty. */
    changenote: string
}

/** A mod the backend filtered out up front. */
export interface BatchPublishSkipped {
    /** As submitted, possibly empty or invalid. */
    workshop_id: string
    title: string
    /** E.g. `"no workshopId"` or `"invalid workshopId"`. */
    reason: string
}

/** Handle returned by `publishAllPacks` for the queued batch. */
export interface BatchPublishHandle {
    batch_id: string
    started_at: string
    /** Mods that passed the workshop_id filter. */
    queued: number
    skipped: BatchPublishSkipped[]
}
