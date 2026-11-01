import { gameApi } from "../../api/games"

const api = gameApi("total_war_warhammer_3")

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

/**
 * Fetch the validation report from the TW3 backend.
 *
 * @returns The issues, empty when all references resolve.
 */
export async function fetchValidation(): Promise<ValidationIssue[]> {
    const res = await api.get("/validation")
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.issues as ValidationIssue[]
}

/**
 * Fetch the read-only `SUPPORTED_MODS` registry from the TW3 backend.
 *
 * @returns The mod entries.
 */
export async function fetchSupportedMods(): Promise<SupportedMod[]> {
    const res = await api.get("/supported-mods")
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.mods as SupportedMod[]
}

/**
 * Start a script run on the backend.
 *
 * @param scriptId Key into the backend `SCRIPT_REGISTRY`.
 * @returns The run handle.
 */
export async function startRun(scriptId: string): Promise<{ run_id: string; script_id: string; started_at: string }> {
    const res = await api.post(`/run/${scriptId}`)
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Poll the backend for the current run state.
 *
 * @returns The idle or running state.
 */
export async function getCurrentRun(): Promise<RunState> {
    const res = await api.get("/run")
    if (!res.ok) throw new Error(`getCurrentRun failed: ${res.status}`)
    return res.json()
}

/**
 * Cancel the active run, if any. A 404 is swallowed so this is idempotent.
 */
export async function cancelRun(): Promise<void> {
    const res = await fetch(api.url("/run"), { method: "DELETE" })
    if (!res.ok && res.status !== 404) {
        throw new Error(`cancelRun failed: ${res.status}`)
    }
}

/**
 * Build the SSE stream URL for the runner log.
 *
 * @returns Absolute URL for `EventSource`.
 */
export function runStreamUrl(): string {
    return api.url("/run/stream")
}

/** Handle returned by `publishPack` for the spawned SteamCMD subprocess. */
export interface PublishHandle {
    publish_id: string
    workshop_id: string
    started_at: string
}

/**
 * Spawn SteamCMD to push the local workshop folder as an update to an existing Workshop item.
 *
 * @param workshopId Workshop item id to update.
 * @param changenote Changelog text, omitted from the VDF when empty.
 * @returns The publish handle.
 */
export async function publishPack(workshopId: string, changenote: string): Promise<PublishHandle> {
    const res = await api.post(`/packs/${encodeURIComponent(workshopId)}/publish`, { changenote })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Build the SSE stream URL for an in-flight publish.
 *
 * @param workshopId Workshop item id to follow.
 * @returns Absolute URL for `EventSource`.
 */
export function publishStreamUrl(workshopId: string): string {
    return api.url(`/packs/${encodeURIComponent(workshopId)}/publish/stream`)
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

/**
 * Generate a changenote per Workshop item from what changed since its last upload.
 *
 * @param ids Workshop ids of compat packs and/or translation mods.
 * @returns The notes and any generator errors, defaulting to empty.
 */
export async function fetchChangeNotes(ids: string[]): Promise<ChangeNotesResponse> {
    const res = await api.post("/packs/change-notes", { ids })
    if (!res.ok) throw await registryError(res)
    const body = (await res.json()) as Partial<ChangeNotesResponse>
    return { notes: body.notes ?? {}, errors: body.errors ?? [] }
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

/**
 * Queue a batch that publishes every supplied mod to the Workshop, each with its own changelog.
 *
 * @param items Mods in run order. Empty or invalid workshop_ids are filtered server-side.
 * @returns The batch handle, whose `batch_id` feeds `publishAllStreamUrl`.
 */
export async function publishAllPacks(items: BatchPublishItem[]): Promise<BatchPublishHandle> {
    const res = await api.post("/packs/publish-all", { items })
    if (!res.ok) throw await registryError(res)
    return res.json()
}

/**
 * Build the SSE URL for the batch publish stream.
 *
 * @param batchId The `batch_id` from `publishAllPacks`.
 * @returns Absolute URL for `EventSource`.
 */
export function publishAllStreamUrl(batchId: string): string {
    return api.url(`/packs/publish-all/stream/${encodeURIComponent(batchId)}`)
}

/** Backend registry/runner error with status, detail, and optional missing list. */
export class RegistryError extends Error {
    status: number
    detail: string
    missing: string[] | null

    constructor(status: number, detail: string, missing: string[] | null) {
        super(detail)
        this.status = status
        this.detail = detail
        this.missing = missing
    }
}

/**
 * Create a new SUPPORTED_MODS entry.
 *
 * @param entry Full entry payload.
 * @returns The reloaded list.
 */
export async function createSupportedMod(entry: Record<string, unknown>): Promise<SupportedMod[]> {
    const res = await api.post("/supported-mods", { entry })
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.mods as SupportedMod[]
}

/**
 * Replace an existing SUPPORTED_MODS entry by its `package_name`.
 *
 * @param packageName Entry to replace.
 * @param entry Replacement payload.
 * @returns The reloaded list.
 */
export async function updateSupportedMod(packageName: string, entry: Record<string, unknown>): Promise<SupportedMod[]> {
    const res = await api.put(`/supported-mods/${encodeURIComponent(packageName)}`, { entry })
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.mods as SupportedMod[]
}

/**
 * Remove a SUPPORTED_MODS entry by its `package_name`.
 *
 * @param packageName Entry to remove.
 * @returns The reloaded list.
 */
export async function deleteSupportedMod(packageName: string): Promise<SupportedMod[]> {
    const res = await api.delete(`/supported-mods/${encodeURIComponent(packageName)}`)
    if (!res.ok) throw await registryError(res)
    const body = await res.json()
    return body.mods as SupportedMod[]
}

/**
 * Fetch the SUPPORTED_EFFECTS category names for the Modified Attributes autocomplete.
 *
 * @returns Sorted category names.
 */
export async function fetchSupportedEffectsCategories(): Promise<string[]> {
    const res = await api.get("/supported-effects")
    if (!res.ok) return []
    const body = await res.json()
    return (body.categories ?? []) as string[]
}

async function registryError(res: Response): Promise<RegistryError> {
    let detail = res.statusText
    let missing: string[] | null = null
    try {
        const body = await res.json()
        if (typeof body.detail === "string") detail = body.detail
        else if (body.detail && Array.isArray(body.detail.missing)) missing = body.detail.missing
    } catch {
        /* ignore */
    }
    return new RegistryError(res.status, detail, missing)
}
