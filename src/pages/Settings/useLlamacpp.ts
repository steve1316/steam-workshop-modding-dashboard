import { useState } from "react"
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query"
import { API_BASE, fetchJson } from "@/lib/api"
import { readEventStream } from "@/lib/stream"
import type { GgufTier, StreamProgress } from "@/pages/Settings/constants"
import type { SettingsForm, SettingsFormState } from "@/pages/Settings/useSettingsForm"

/** Body of `GET /api/llamacpp/status`. */
interface LlamacppStatus {
    status: string
    /** True once llama-server is on disk. */
    installed?: boolean
}

/** A GGUF file in the backend's model folder. */
export interface LocalModel {
    name: string
    path: string
    /** Bytes. */
    size: number
}

const POLL_MS = 10000

/**
 * Save llama.cpp fields straight to the backend without waiting, for values the user picked rather than typed.
 *
 * @param patch Fields to save.
 */
function saveInBackground(patch: Partial<SettingsForm>) {
    // A failed save leaves the value as a pending change the next Save sends.
    fetch(`${API_BASE}/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }).catch(() => {})
}

/**
 * The local llama.cpp server: its polled status and downloaded GGUF models, and the tier, download, delete and install actions.
 *
 * @param settings The Settings form. Polling runs only while llama.cpp is the selected provider.
 * @returns The server state and its actions.
 */
export function useLlamacpp(settings: SettingsFormState) {
    const { form, update, markSaved } = settings
    const active = form.provider === "llamacpp"
    const queryClient = useQueryClient()
    const [downloading, setDownloading] = useState(false)
    const [downloadProgress, setDownloadProgress] = useState<StreamProgress | null>(null)
    const [installing, setInstalling] = useState(false)
    const [installProgress, setInstallProgress] = useState<StreamProgress | null>(null)

    // The saved URL is in the key so saving a new one checks it right away.
    const statusKey = ["llamacpp-status", settings.saved.llamacpp_base_url]
    const { data: statusData } = useQuery({
        queryKey: statusKey,
        queryFn: () => fetchJson<LlamacppStatus>(`${API_BASE}/llamacpp/status`).catch(() => ({ status: "not_running", installed: false })),
        // Paused during install or download so a poll cannot reset their state.
        enabled: active && !installing && !downloading,
        refetchInterval: POLL_MS,
        placeholderData: keepPreviousData,
    })
    const { data: localModels = [], refetch: refetchModels } = useQuery({
        queryKey: ["llamacpp-models"],
        queryFn: () => fetchJson<{ models?: LocalModel[] }>(`${API_BASE}/llamacpp/models`).then((body) => body.models ?? []),
        enabled: active,
    })

    /**
     * Pick a VRAM tier, or clear it when it is already picked. A tier whose GGUF is already downloaded is saved at once.
     *
     * @param tier The tier clicked.
     */
    const selectTier = (tier: GgufTier) => {
        if (form.llamacpp_vram_tier === tier.tier) {
            update({ llamacpp_vram_tier: "", llamacpp_model: "" })
            return
        }
        const local = localModels.find((m) => m.name === tier.filename)
        if (!local) {
            update({ llamacpp_vram_tier: tier.tier, llamacpp_model: tier.model })
            return
        }
        const patch = { llamacpp_model_path: local.path, llamacpp_model: tier.model, llamacpp_vram_tier: tier.tier }
        markSaved(patch)
        saveInBackground(patch)
    }

    /**
     * Download a tier's GGUF, streaming its progress, and save it as the model once it lands.
     *
     * @param tier The tier to download.
     */
    const download = async (tier: GgufTier) => {
        setDownloading(true)
        setDownloadProgress(null)
        try {
            const res = await fetch(`${API_BASE}/llamacpp/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: tier.url, filename: tier.filename }),
            })
            await readEventStream<StreamProgress>(res, (progress) => {
                setDownloadProgress(progress)
                if (progress.status === "done" && progress.path) {
                    const patch = { llamacpp_model_path: progress.path, llamacpp_model: tier.model, llamacpp_vram_tier: tier.tier }
                    markSaved(patch)
                    saveInBackground(patch)
                }
                if (progress.status === "error") console.error("GGUF download error:", progress.message)
            })
            refetchModels()
        } catch (err) {
            console.error("Failed to download GGUF:", err)
        } finally {
            setDownloading(false)
            setDownloadProgress(null)
        }
    }

    /**
     * Delete a downloaded GGUF, clearing the model path when it pointed at that file.
     *
     * @param filename The GGUF file name.
     */
    const deleteModel = async (filename: string) => {
        try {
            const res = await fetch(`${API_BASE}/llamacpp/models/${encodeURIComponent(filename)}`, { method: "DELETE" })
            if (!res.ok) return
            refetchModels()
            const deleted = localModels.find((m) => m.name === filename)
            if (deleted && form.llamacpp_model_path === deleted.path) update({ llamacpp_model_path: "" })
        } catch (err) {
            console.error("Failed to delete model:", err)
        }
    }

    /**
     * Download and unpack a llama-server build, streaming its progress.
     *
     * @param backend Build to fetch, such as `cuda-12` or `vulkan`.
     */
    const install = async (backend: string) => {
        setInstalling(true)
        setInstallProgress(null)
        try {
            const res = await fetch(`${API_BASE}/llamacpp/install`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ backend }) })
            await readEventStream<StreamProgress>(res, (progress) => {
                setInstallProgress(progress)
                if (progress.status !== "done") return
                queryClient.setQueryData<LlamacppStatus>(statusKey, (old) => ({ status: old?.status ?? "unknown", installed: true }))
                if (progress.binary_path) markSaved({ llamacpp_binary_path: progress.binary_path })
            })
        } catch (err) {
            console.error("Failed to install llama-server:", err)
        } finally {
            setInstalling(false)
            setInstallProgress(null)
        }
    }

    return {
        /** `unknown` until the first check answers. */
        status: statusData?.status ?? "unknown",
        installed: statusData?.installed ?? false,
        localModels,
        downloading,
        downloadProgress,
        installing,
        installProgress,
        selectTier,
        download,
        deleteModel,
        install,
    }
}

export type LlamacppState = ReturnType<typeof useLlamacpp>
