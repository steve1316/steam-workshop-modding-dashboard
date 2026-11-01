import type {
    Glossary,
    TermSuggestion,
    ApiLogEntry,
    WH3DriftRow,
    WH3DriftStatus,
    WH3GlossaryEntry,
    WH3ModContext,
    WH3RescanSummary,
    WH3SnapshotMeta,
    WH3SyncResult,
    WH3TranslationModSummary,
} from "../../shared_types"
import { gameApi } from "../../api/games"
import type { TranslationPreview } from "../../components/TranslationConfirmModal"
import type { BatchDescriptor } from "../../hooks/useIterativeTranslation"
import { RegistryError } from "./api"

/** Preview response for a WH3 translation run: the confirm-modal data plus the flat `batch_plan`. */
export type WH3TranslationPreview = TranslationPreview & {
    total_strings: number
    batch_plan: BatchDescriptor[]
    /** Present only when `total_strings` is 0. */
    message?: string
    /** Translate Names previews only, in run order. */
    stages?: WH3NameStage[]
}

/** One stage of the Translate Names pass, reviewed into the glossary before the next stage runs. */
export type WH3NameStage = {
    id: string
    label: string
    /** Name categories this stage covers, used to fetch only its names for review. */
    categories: string[]
    total_strings: number
    batch_plan: BatchDescriptor[]
}

const api = gameApi("total_war_warhammer_3")

/**
 * List all registered WH3 translation mods.
 *
 * @returns One summary row per mod.
 */
export async function listTranslationMods(): Promise<WH3TranslationModSummary[]> {
    const res = await api.get("/translation/mods")
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Re-extract parent strings, re-read local translations, and recompute drift.
 *
 * @param workshopId Translation mod Workshop id.
 * @param signal Aborts the request.
 * @returns Status counts and scan time.
 */
export async function rescanMod(workshopId: string, signal?: AbortSignal): Promise<WH3RescanSummary> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/rescan`, undefined, { signal })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Fetch drift rows for a mod, optionally filtered by status.
 *
 * @param workshopId Translation mod Workshop id.
 * @param status Drift status filter.
 * @returns Rows sorted by `(filename, key)`.
 */
export async function fetchStrings(workshopId: string, status?: WH3DriftStatus): Promise<WH3DriftRow[]> {
    const path = `/translation/mods/${encodeURIComponent(workshopId)}/strings${status ? `?status=${status}` : ""}`
    const res = await api.get(path)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Save a translation edit for one row. Writes `translations.json` only, not the `.loc.tsv`.
 *
 * @param workshopId Translation mod Workshop id.
 * @param key Localization key.
 * @param text New translation text.
 */
export async function saveString(workshopId: string, key: string, text: string): Promise<void> {
    const res = await api.put(`/translation/mods/${encodeURIComponent(workshopId)}/strings/${encodeURIComponent(key)}`, { text })
    if (!res.ok) throw await registryError(res)
}

/**
 * Fetch the per-mod context used in LLM translation prompts.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns The mod context.
 */
export async function fetchModContext(workshopId: string): Promise<WH3ModContext> {
    const res = await api.get(`/translation/mods/${encodeURIComponent(workshopId)}/mod-context`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Save the per-mod context.
 *
 * @param workshopId Translation mod Workshop id.
 * @param ctx Context to save.
 */
export async function saveModContext(workshopId: string, ctx: WH3ModContext): Promise<void> {
    const res = await api.put(`/translation/mods/${encodeURIComponent(workshopId)}/mod-context`, ctx)
    if (!res.ok) throw await registryError(res)
}

/**
 * Preview a translation run (prompts, cost, batch plan). Mirrors Chrono Ark's `/translate/preview` so the shared modal and hook drive both games.
 *
 * @param workshopId Translation mod Workshop id.
 * @param provider Overrides the server's provider.
 * @param scope Which rows to cover: all untranslated, names only, or changed rows only.
 * @returns The preview, with `total_strings` 0 when nothing is untranslated.
 */
export async function previewTranslation(workshopId: string, provider?: string, scope: "all" | "names" | "changed" = "all"): Promise<WH3TranslationPreview> {
    const res = await api.post("/translate/preview", { mod_id: workshopId, provider, scope })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Accept the current source text as the baseline for changed rows, keeping their translations.
 *
 * @param workshopId Translation mod Workshop id.
 * @param keys Keys to accept, or all changed rows when omitted.
 * @returns Accepted count.
 */
export async function acceptChanged(workshopId: string, keys?: string[]): Promise<number> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/accept-changed`, { keys: keys ?? null })
    if (!res.ok) throw await registryError(res)
    return (await res.json()).accepted
}

/**
 * Build and save glossary suggestions from translated name rows the glossary does not cover yet.
 *
 * @param workshopId Translation mod Workshop id.
 * @param categories Name categories to limit to (one stage), or all when omitted.
 * @returns The new suggestions.
 */
export async function loadNameSuggestions(workshopId: string, categories?: string[]): Promise<TermSuggestion[]> {
    const res = await api.post("/translate/name-suggestions", categories ? { mod_id: workshopId, categories } : { mod_id: workshopId })
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.suggestions ?? []
}

/**
 * Patch `translations.json` into the `.loc.tsv` files.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns The sync result.
 */
export async function syncChanges(workshopId: string): Promise<WH3SyncResult> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/sync`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Wipe every translated `text` for the mod.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns Cleared count.
 */
export async function clearTranslations(workshopId: string): Promise<{ cleared: number }> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/clear-translations`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Fetch snapshot metadata for a mod.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns Snapshots, newest first.
 */
export async function listSnapshots(workshopId: string): Promise<WH3SnapshotMeta[]> {
    const res = await api.get(`/translation/mods/${encodeURIComponent(workshopId)}/snapshots`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Create a manual snapshot of the mod's current state.
 *
 * @param workshopId Translation mod Workshop id.
 * @param label Snapshot label.
 * @returns The new snapshot.
 */
export async function createSnapshot(workshopId: string, label: string): Promise<WH3SnapshotMeta> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/snapshots`, { label })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Restore a mod from a snapshot. The backend takes a pre-restore snapshot first.
 *
 * @param workshopId Translation mod Workshop id.
 * @param ulid Snapshot id.
 */
export async function restoreSnapshot(workshopId: string, ulid: string): Promise<void> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/snapshots/${encodeURIComponent(ulid)}/restore`)
    if (!res.ok) throw await registryError(res)
}

/**
 * Delete one snapshot from a mod's history.
 *
 * @param workshopId Translation mod Workshop id.
 * @param ulid Snapshot id.
 */
export async function deleteSnapshot(workshopId: string, ulid: string): Promise<void> {
    const res = await api.delete(`/translation/mods/${encodeURIComponent(workshopId)}/snapshots/${encodeURIComponent(ulid)}`)
    if (!res.ok) throw await registryError(res)
}

/**
 * Fetch the per-mod glossary.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns Terms keyed by English.
 */
export async function loadGlossary(workshopId: string): Promise<Record<string, { source: string; category: string }>> {
    const res = await api.get(`/translation/mods/${encodeURIComponent(workshopId)}/glossary`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Fetch the WH3 base-game terminology glossary.
 *
 * @returns The base glossary.
 */
export async function fetchBaseGlossary(): Promise<Glossary> {
    const res = await api.get("/translation/glossary")
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Add or replace one glossary entry.
 *
 * @param workshopId Translation mod Workshop id.
 * @param entry Entry to save.
 */
export async function addGlossaryTerm(workshopId: string, entry: WH3GlossaryEntry): Promise<void> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/glossary`, entry)
    if (!res.ok) throw await registryError(res)
}

/**
 * Update one glossary entry. A new English also renames the old one in translations whose source contains the term's source.
 *
 * @param workshopId Translation mod Workshop id.
 * @param oldEnglish Current English key.
 * @param entry New entry, whose `english` may differ to rename.
 * @returns Rename count.
 */
export async function updateGlossaryTerm(workshopId: string, oldEnglish: string, entry: WH3GlossaryEntry): Promise<{ replaced: number }> {
    const res = await api.put(`/translation/mods/${encodeURIComponent(workshopId)}/glossary/${encodeURIComponent(oldEnglish)}`, entry)
    if (!res.ok) throw await registryError(res)
    const body = await res.json().catch(() => ({}))
    return { replaced: typeof body?.replaced === "number" ? body.replaced : 0 }
}

/**
 * Delete one glossary entry.
 *
 * @param workshopId Translation mod Workshop id.
 * @param english English term.
 */
export async function deleteGlossaryTerm(workshopId: string, english: string): Promise<void> {
    const res = await api.delete(`/translation/mods/${encodeURIComponent(workshopId)}/glossary/${encodeURIComponent(english)}`)
    if (!res.ok) throw await registryError(res)
}

/**
 * Delete every glossary entry. The backend saves a History snapshot first.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns Deleted count.
 */
export async function deleteAllGlossaryTerms(workshopId: string): Promise<{ status: string; deleted: number }> {
    const res = await api.delete(`/translation/mods/${encodeURIComponent(workshopId)}/glossary`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Rename `oldEnglish` to `newEnglish` as a whole term in every translation of the mod.
 *
 * @param workshopId Translation mod Workshop id.
 * @param oldEnglish Term to replace.
 * @param newEnglish Replacement term.
 * @returns Count of changed translations.
 */
export async function glossaryApplyAll(workshopId: string, oldEnglish: string, newEnglish: string): Promise<{ replaced: number }> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/glossary/apply-all`, { old_english: oldEnglish, new_english: newEnglish })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Ask the LLM for glossary refinements and save them as pending suggestions. Logs to api_responses.
 *
 * @param workshopId Translation mod Workshop id.
 * @returns New suggestion count.
 */
export async function glossarySuggestEdits(workshopId: string): Promise<{ status: string; new: number }> {
    const res = await api.post(`/mods/${encodeURIComponent(workshopId)}/glossary/suggest-edits`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Fetch the audit log of recent LLM calls (newest first, capped at 20).
 *
 * @param workshopId Translation mod Workshop id.
 * @returns Audit entries.
 */
export async function listApiResponses(workshopId: string): Promise<ApiLogEntry[]> {
    const res = await api.get(`/translation/mods/${encodeURIComponent(workshopId)}/api-responses`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Open the mod's source directory in the file explorer.
 *
 * @param workshopId Translation mod Workshop id.
 */
export async function openModFolder(workshopId: string): Promise<void> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/open-folder`)
    if (!res.ok) throw await registryError(res)
}

/**
 * Open a source `.loc.tsv` file in the default app.
 *
 * @param workshopId Translation mod Workshop id.
 * @param filename Normalized filename from the Source column.
 */
export async function openSourceFile(workshopId: string, filename: string): Promise<void> {
    const res = await api.post(`/translation/mods/${encodeURIComponent(workshopId)}/open-source-file/${encodeURIComponent(filename)}`)
    if (!res.ok) throw await registryError(res)
}

async function registryError(res: Response): Promise<RegistryError> {
    let detail = res.statusText
    try {
        const body = await res.json()
        if (typeof body.detail === "string") detail = body.detail
    } catch {
        /* ignore */
    }
    return new RegistryError(res.status, detail, null)
}
