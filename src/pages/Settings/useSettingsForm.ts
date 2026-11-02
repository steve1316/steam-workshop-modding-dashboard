import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { API_BASE, fetchJson } from "@/lib/api"
import { listGames } from "@/games/registry"
import type { KeyField } from "@/pages/Settings/constants"

/** The editable settings, keyed by the `/api/settings` field each one saves to. */
export interface SettingsForm {
    provider: string
    batch_size: number
    claude_model: string
    openai_model: string
    /** Typed but not saved yet. Blank means no change, since the backend never returns a saved key. */
    anthropic_api_key: string
    openai_api_key: string
    deepl_api_key: string
    ollama_base_url: string
    ollama_model: string
    ollama_vram_tier: string
    llamacpp_base_url: string
    llamacpp_model: string
    llamacpp_binary_path: string
    llamacpp_model_path: string
    llamacpp_gpu_layers: number
    llamacpp_ctx_size: number
    llamacpp_vram_tier: string
    ignored_mods: string[]
    /** Every registered game's `settingsPanel.keys`, kept apart because the set depends on which games are registered. */
    game: Record<string, string>
}

/** The values a missing or blank field falls back to. */
export const DEFAULT_FORM: SettingsForm = {
    provider: "claude",
    batch_size: 100,
    claude_model: "claude-sonnet-5",
    openai_model: "gpt-4.1",
    anthropic_api_key: "",
    openai_api_key: "",
    deepl_api_key: "",
    ollama_base_url: "http://localhost:11434",
    ollama_model: "qwen2.5:7b",
    ollama_vram_tier: "",
    llamacpp_base_url: "http://localhost:8080",
    llamacpp_model: "",
    llamacpp_binary_path: "llama-server",
    llamacpp_model_path: "",
    llamacpp_gpu_layers: -1,
    llamacpp_ctx_size: 8192,
    llamacpp_vram_tier: "",
    ignored_mods: [],
    game: {},
}

const SETTINGS_KEY = ["settings"]

type SettingsResponse = Record<string, unknown>

/**
 * Read the form out of a `/api/settings` response, using the default for any field that is missing or blank.
 *
 * @param data The response body.
 * @returns The saved form.
 */
export function formFromResponse(data: SettingsResponse): SettingsForm {
    const form: Record<string, unknown> = {}
    for (const [key, fallback] of Object.entries(DEFAULT_FORM)) {
        const value = data[key]
        if (typeof fallback === "string") form[key] = typeof value === "string" && value !== "" ? value : fallback
        else if (typeof fallback === "number") form[key] = typeof value === "number" ? value : fallback
        else if (Array.isArray(fallback)) form[key] = Array.isArray(value) ? value : fallback
    }
    const gameKeys = listGames().flatMap((game) => game.settingsPanel?.keys ?? [])
    form.game = Object.fromEntries(gameKeys.map((key) => [key, typeof data[key] === "string" ? data[key] : ""]))
    // The response never holds a saved key, so a blank field here means nothing new was typed.
    form.anthropic_api_key = form.openai_api_key = form.deepl_api_key = ""
    return form as unknown as SettingsForm
}

/**
 * Flatten part of a form into `/api/settings` fields.
 *
 * @param patch Form fields to send.
 * @returns The fields as the backend names them.
 */
function toFields(patch: Partial<SettingsForm>): SettingsResponse {
    const { game, ...rest } = patch
    return { ...rest, ...game }
}

/**
 * Apply a partial form on top of a form. Game values merge one level down so one game's edit keeps the others.
 *
 * @param base The form to change.
 * @param patch Fields to overwrite.
 * @returns The merged form.
 */
function merge<T extends Partial<SettingsForm>>(base: T, patch: Partial<SettingsForm>): T {
    return { ...base, ...patch, game: { ...base.game, ...patch.game } }
}

/**
 * The fields that differ between the draft and the saved form, ready to POST.
 *
 * @param draft The form as edited.
 * @param saved The form as last loaded or saved.
 * @returns Changed fields as the backend names them. Empty when nothing changed.
 */
export function diffSettings(draft: SettingsForm, saved: SettingsForm): SettingsResponse {
    const before = toFields(saved)
    return Object.fromEntries(Object.entries(toFields(draft)).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(before[key])))
}

/**
 * The Settings form: the saved settings from `/api/settings` with the unsaved edits laid on top. Save sends only the fields that differ, so a
 * field nobody touched is never overwritten.
 *
 * @returns The draft and saved forms, load and save state, and the edit and save actions.
 */
export function useSettingsForm() {
    const queryClient = useQueryClient()
    const { data, error, isPending, isFetching, refetch } = useQuery({ queryKey: SETTINGS_KEY, queryFn: () => fetchJson<SettingsResponse>(`${API_BASE}/settings`) })
    const [edits, setEdits] = useState<Partial<SettingsForm>>({})
    const [saving, setSaving] = useState(false)
    const [saveSuccess, setSaveSuccess] = useState(false)
    // Why the last Save failed, shown in a banner above the Save button until dismissed or the next Save.
    const [saveError, setSaveError] = useState<string | null>(null)

    const saved = data ? formFromResponse(data) : DEFAULT_FORM
    const form = merge(saved, edits)
    const changes = diffSettings(form, saved)

    /**
     * Edit the draft.
     *
     * @param patch Fields to change.
     */
    const update = (patch: Partial<SettingsForm>) => setEdits((prev) => merge(prev, patch))

    /**
     * Record values the backend already saved, such as a downloaded model's path, so they are not pending changes.
     *
     * @param patch Fields the backend now holds.
     */
    const markSaved = (patch: Partial<SettingsForm>) => {
        queryClient.setQueryData<SettingsResponse>(SETTINGS_KEY, (old) => old && { ...old, ...toFields(patch) })
        update(patch)
    }

    /** Send the changed fields and take the response as the new saved form. */
    const save = async () => {
        setSaving(true)
        setSaveSuccess(false)
        setSaveError(null)
        try {
            const res = await fetch(`${API_BASE}/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) })
            const body = await res.json()
            if (!res.ok) throw new Error(body.detail || "Save failed")
            queryClient.setQueryData(SETTINGS_KEY, body)
            setEdits({})
            setSaveSuccess(true)
            setTimeout(() => setSaveSuccess(false), 3000)
        } catch (err) {
            console.error("Failed to save settings:", err)
            setSaveError(`Could not save settings: ${err instanceof Error ? err.message : String(err)}`)
        } finally {
            setSaving(false)
        }
    }

    const keyStatus = Object.fromEntries((["anthropic", "openai", "deepl"] as const).map((field) => [field, String(data?.[`${field}_api_key_set`] ?? "")])) as Record<KeyField, string>

    return {
        form,
        saved,
        keyStatus,
        loading: isPending,
        // Hidden while a retry is in flight so the loading state shows instead.
        loadError: error && !isFetching ? error.message : null,
        reload: refetch,
        update,
        markSaved,
        isChanged: Object.keys(changes).length > 0,
        save,
        saving,
        saveSuccess,
        saveError,
        dismissSaveError: () => setSaveError(null),
    }
}

export type SettingsFormState = ReturnType<typeof useSettingsForm>
