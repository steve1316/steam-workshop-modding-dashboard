import { useState } from "react"
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query"
import { API_BASE, fetchJson } from "@/lib/api"
import { readEventStream } from "@/lib/stream"
import type { StreamProgress } from "@/pages/Settings/constants"
import type { SettingsFormState } from "@/pages/Settings/useSettingsForm"

/** Body of `GET /api/ollama/status`. */
interface OllamaStatus {
    status: string
    models: { name: string }[]
    /** True when the dashboard started the server and can stop it. */
    managed?: boolean
}

const POLL_MS = 10000

const NOT_INSTALLED: OllamaStatus = { status: "not_installed", models: [], managed: false }

/**
 * The local Ollama server: its polled status and installed models, and the install, pull, start and stop actions.
 *
 * @param settings The Settings form. Polling runs only while Ollama is the selected provider.
 * @returns The server state and its actions.
 */
export function useOllama(settings: SettingsFormState) {
    const queryClient = useQueryClient()
    // The saved URL is in the key so saving a new one checks it right away.
    const queryKey = ["ollama-status", settings.saved.ollama_base_url]
    const { data, refetch } = useQuery({
        queryKey,
        // A failed check means nothing answered, which the panel shows as not installed.
        queryFn: () => fetchJson<OllamaStatus>(`${API_BASE}/ollama/status`).catch(() => NOT_INSTALLED),
        enabled: settings.form.provider === "ollama",
        refetchInterval: POLL_MS,
        placeholderData: keepPreviousData,
    })
    const [installing, setInstalling] = useState(false)
    const [pulling, setPulling] = useState(false)
    const [pullProgress, setPullProgress] = useState<StreamProgress | null>(null)
    const [starting, setStarting] = useState(false)
    const [stopping, setStopping] = useState(false)

    const install = async () => {
        setInstalling(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/install`, { method: "POST" })
            const body = await res.json()
            if (!res.ok) throw new Error(body.detail)
        } catch (err) {
            console.error("Failed to install Ollama:", err)
        } finally {
            setInstalling(false)
        }
    }

    /**
     * Download a model into Ollama, streaming its progress.
     *
     * @param model Ollama model tag.
     */
    const pull = async (model: string) => {
        setPulling(true)
        setPullProgress(null)
        try {
            const res = await fetch(`${API_BASE}/ollama/pull`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model }) })
            await readEventStream<StreamProgress>(res, (progress) => {
                setPullProgress(progress)
                return progress.status === "done"
            })
            refetch()
        } catch (err) {
            console.error("Failed to pull model:", err)
        } finally {
            setPulling(false)
            setPullProgress(null)
        }
    }

    const start = async () => {
        setStarting(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/start`, { method: "POST" })
            const body = await res.json()
            if (!res.ok) throw new Error(body.detail)
            await refetch()
        } catch (err) {
            console.error("Failed to start Ollama:", err)
        } finally {
            setStarting(false)
        }
    }

    const stop = async () => {
        setStopping(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/stop`, { method: "POST" })
            if (!res.ok) {
                const body = await res.json()
                throw new Error(body.detail)
            }
            queryClient.setQueryData<OllamaStatus>(queryKey, (old) => ({ ...(old ?? NOT_INSTALLED), status: "stopped", managed: false }))
        } catch (err) {
            console.error("Failed to stop Ollama:", err)
        } finally {
            setStopping(false)
        }
    }

    return {
        /** `unknown` until the first check answers. */
        status: data?.status ?? "unknown",
        models: data?.models.map((m) => m.name) ?? [],
        managed: data?.managed ?? false,
        installing,
        pulling,
        pullProgress,
        starting,
        stopping,
        install,
        pull,
        start,
        stop,
    }
}

export type OllamaState = ReturnType<typeof useOllama>
