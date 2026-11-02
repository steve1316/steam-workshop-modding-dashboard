import React, { useEffect, useId, useState } from "react"
import { FaEye, FaEyeSlash, FaCheck, FaExclamationTriangle, FaChevronDown, FaChevronRight, FaDownload, FaPlay, FaStop, FaTimes } from "react-icons/fa"
import { API_BASE, gameApi } from "@/lib/api"
import { getGame, listGames } from "@/games/registry"
import ErrorState from "@/components/ui/ErrorState"
import Banner from "@/components/ui/Banner"
import DownloadProgress from "@/components/ui/DownloadProgress"
import Field from "@/components/ui/Field"
import LoadingState from "@/components/ui/LoadingState"
import PageHeader from "@/components/ui/PageHeader"
import Panel from "@/components/ui/Panel"

/** Tracks user-entered API key values (empty string = no pending change). */
interface KeyState {
    anthropic: string
    openai: string
    deepl: string
}

/** Available translation providers, mapping a backend provider id to its label, description, and API key field (`null` when no credentials are needed). */
const PROVIDERS = [
    { id: "claude", label: "Claude", description: "Anthropic", keyField: "anthropic" as const },
    { id: "openai", label: "OpenAI", description: "OpenAI", keyField: "openai" as const },
    { id: "deepl", label: "DeepL", description: "Neural Machine Translation", keyField: "deepl" as const },
    { id: "ollama", label: "Ollama (Local)", description: "Free local AI — no API key needed", keyField: null },
    { id: "llamacpp", label: "llama.cpp (Local)", description: "Direct llama-server connection", keyField: null },
    { id: "manual", label: "Manual", description: "Translate by hand in the app", keyField: null },
]

/** VRAM tier to recommended Ollama model mapping. */
const VRAM_TIERS = [
    { tier: "4-6gb", label: "4-6 GB", model: "gemma3:4b", description: "Google multilingual small", size: "3.3 GB" },
    { tier: "8gb", label: "8 GB", model: "qwen2.5:7b", description: "Alibaba, excellent CJK", size: "4.7 GB" },
    { tier: "12gb", label: "12 GB", model: "qwen2.5:14b", description: "Larger Qwen, better quality", size: "9.0 GB" },
    { tier: "16gb", label: "16 GB", model: "mistral-small:22b", description: "Strong reasoning", size: "13 GB" },
    { tier: "24gb+", label: "24 GB+", model: "qwen2.5:32b", description: "Near-API quality", size: "20 GB" },
]

/** VRAM tier to recommended GGUF model mapping for llama.cpp. Single-file quantizations from bartowski. */
const GGUF_TIERS = [
    {
        tier: "4-6gb",
        label: "4-6 GB",
        model: "Qwen2.5-3B-Instruct",
        description: "Alibaba, fast CJK",
        size: "1.8 GB",
        filename: "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        url: "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
    },
    {
        tier: "8gb",
        label: "8 GB",
        model: "Qwen2.5-7B-Instruct",
        description: "Alibaba, excellent CJK",
        size: "4.4 GB",
        filename: "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        url: "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    },
    {
        tier: "12gb",
        label: "12 GB",
        model: "Qwen2.5-14B-Instruct",
        description: "Larger Qwen, better quality",
        size: "8.4 GB",
        filename: "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        url: "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
    },
    {
        tier: "16gb",
        label: "16 GB",
        model: "Qwen2.5-14B-Instruct",
        description: "Higher quality quantization",
        size: "14.6 GB",
        filename: "Qwen2.5-14B-Instruct-Q8_0.gguf",
        url: "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q8_0.gguf",
    },
    {
        tier: "24gb+",
        label: "24 GB+",
        model: "Qwen2.5-32B-Instruct",
        description: "Near-API quality",
        size: "18.5 GB",
        filename: "Qwen2.5-32B-Instruct-Q4_K_M.gguf",
        url: "https://huggingface.co/bartowski/Qwen2.5-32B-Instruct-GGUF/resolve/main/Qwen2.5-32B-Instruct-Q4_K_M.gguf",
    },
]

/** Props for SettingsPage. */
interface SettingsPageProps {
    /** Game shown in the sidebar. The system prompt preview loads from its backend. */
    gameId: string
}

/**
 * Read every registered game's settings fields out of a `/api/settings` response.
 *
 * @param data The response body.
 * @returns Key to value, blank for fields the response leaves out.
 */
function pickGameValues(data: Record<string, unknown>): Record<string, string> {
    const keys = listGames().flatMap((game) => game.settingsPanel?.keys ?? [])
    return Object.fromEntries(keys.map((key) => [key, typeof data[key] === "string" ? (data[key] as string) : ""]))
}

/**
 * Settings page for the translation provider, API keys, and batch size. Changes persist to the backend `.env` and apply without a restart.
 *
 * @param gameId Game whose system prompt the preview loads.
 * @returns The settings page, its loading state, or an error with Retry.
 */
const SettingsPage: React.FC<SettingsPageProps> = ({ gameId }) => {
    // Prefixes every field id so each label can point at its control.
    const fieldId = useId()
    const [provider, setProvider] = useState("claude")
    const [originalProvider, setOriginalProvider] = useState("claude")
    const [batchSize, setBatchSize] = useState(100)
    const [originalBatchSize, setOriginalBatchSize] = useState(100)
    const [apiKeys, setApiKeys] = useState<KeyState>({ anthropic: "", openai: "", deepl: "" })
    const [keyStatus, setKeyStatus] = useState<KeyState>({ anthropic: "", openai: "", deepl: "" })
    const [keyVisible, setKeyVisible] = useState<{ anthropic: boolean; openai: boolean; deepl: boolean }>({
        anthropic: false,
        openai: false,
        deepl: false,
    })
    const [claudeModel, setClaudeModel] = useState("claude-sonnet-5")
    const [originalClaudeModel, setOriginalClaudeModel] = useState("claude-sonnet-5")
    const [openaiModel, setOpenaiModel] = useState("gpt-4.1")
    const [originalOpenaiModel, setOriginalOpenaiModel] = useState("gpt-4.1")
    const [claudeModels, setClaudeModels] = useState<{ id: string; label: string; input_per_mtok: number; output_per_mtok: number }[]>([])
    const [openaiModels, setOpenaiModels] = useState<{ id: string; label: string; input_per_mtok: number; output_per_mtok: number }[]>([])

    const [saving, setSaving] = useState(false)
    const [saveSuccess, setSaveSuccess] = useState(false)
    // Why the last Save failed, shown in a banner above the Save button until dismissed or the next Save.
    const [saveError, setSaveError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    // Why the settings could not be loaded. While set, the page shows an error with Retry instead of a form of defaults.
    const [loadError, setLoadError] = useState<string | null>(null)
    // Bumped by Retry to run the load effect again.
    const [loadAttempt, setLoadAttempt] = useState(0)

    const [ignoredMods, setIgnoredMods] = useState<string[]>([])
    const [originalIgnoredMods, setOriginalIgnoredMods] = useState<string[]>([])
    const [newIgnoredMod, setNewIgnoredMod] = useState("")

    // Values for every game's `settingsPanel.keys`, edited by the panels the manifests supply.
    const [gameValues, setGameValues] = useState<Record<string, string>>({})
    const [originalGameValues, setOriginalGameValues] = useState<Record<string, string>>({})
    const setGameValue = (key: string, value: string) => setGameValues((prev) => ({ ...prev, [key]: value }))
    const markGameValueSaved = (key: string, value: string) => {
        setGameValue(key, value)
        setOriginalGameValues((prev) => ({ ...prev, [key]: value }))
    }

    const [ollamaStatus, setOllamaStatus] = useState<string>("unknown")
    const [ollamaModels, setOllamaModels] = useState<string[]>([])
    const [ollamaBaseUrl, setOllamaBaseUrl] = useState("http://localhost:11434")
    const [originalOllamaBaseUrl, setOriginalOllamaBaseUrl] = useState("http://localhost:11434")
    const [ollamaModel, setOllamaModel] = useState("qwen2.5:7b")
    const [originalOllamaModel, setOriginalOllamaModel] = useState("qwen2.5:7b")
    const [ollamaVramTier, setOllamaVramTier] = useState("")
    const [originalOllamaVramTier, setOriginalOllamaVramTier] = useState("")
    const [ollamaInstalling, setOllamaInstalling] = useState(false)
    const [ollamaPulling, setOllamaPulling] = useState(false)
    const [ollamaPullProgress, setOllamaPullProgress] = useState<{ status: string; completed?: number; total?: number } | null>(null)
    const [showOllamaAdvanced, setShowOllamaAdvanced] = useState(false)

    const [ollamaManaged, setOllamaManaged] = useState(false)
    const [ollamaStarting, setOllamaStarting] = useState(false)
    const [ollamaStopping, setOllamaStopping] = useState(false)

    const [llamacppStatus, setLlamacppStatus] = useState<string>("unknown")
    const [llamacppBaseUrl, setLlamacppBaseUrl] = useState("http://localhost:8080")
    const [originalLlamacppBaseUrl, setOriginalLlamacppBaseUrl] = useState("http://localhost:8080")
    const [llamacppModel, setLlamacppModel] = useState("")
    const [originalLlamacppModel, setOriginalLlamacppModel] = useState("")
    const [llamacppBinaryPath, setLlamacppBinaryPath] = useState("llama-server")
    const [originalLlamacppBinaryPath, setOriginalLlamacppBinaryPath] = useState("llama-server")
    const [llamacppModelPath, setLlamacppModelPath] = useState("")
    const [originalLlamacppModelPath, setOriginalLlamacppModelPath] = useState("")
    const [llamacppGpuLayers, setLlamacppGpuLayers] = useState(-1)
    const [originalLlamacppGpuLayers, setOriginalLlamacppGpuLayers] = useState(-1)
    const [llamacppCtxSize, setLlamacppCtxSize] = useState(8192)
    const [originalLlamacppCtxSize, setOriginalLlamacppCtxSize] = useState(8192)
    const [showLlamacppAdvanced, setShowLlamacppAdvanced] = useState(false)
    const [llamacppVramTier, setLlamacppVramTier] = useState("")
    const [originalLlamacppVramTier, setOriginalLlamacppVramTier] = useState("")
    const [llamacppLocalModels, setLlamacppLocalModels] = useState<{ name: string; path: string; size: number }[]>([])
    const [llamacppDownloading, setLlamacppDownloading] = useState(false)
    const [llamacppDownloadProgress, setLlamacppDownloadProgress] = useState<{ status: string; completed?: number; total?: number } | null>(null)
    const [llamacppInstalled, setLlamacppInstalled] = useState(false)
    const [llamacppInstalling, setLlamacppInstalling] = useState(false)
    const [llamacppInstallProgress, setLlamacppInstallProgress] = useState<{ status: string; file?: string; completed?: number; total?: number } | null>(null)

    const [systemPrompt, setSystemPrompt] = useState("")
    const [promptSourceLang, setPromptSourceLang] = useState("Chinese")
    const [promptLoading, setPromptLoading] = useState(false)

    const isChanged =
        provider !== originalProvider ||
        batchSize !== originalBatchSize ||
        claudeModel !== originalClaudeModel ||
        openaiModel !== originalOpenaiModel ||
        apiKeys.anthropic !== "" ||
        apiKeys.openai !== "" ||
        apiKeys.deepl !== "" ||
        ollamaBaseUrl !== originalOllamaBaseUrl ||
        ollamaModel !== originalOllamaModel ||
        ollamaVramTier !== originalOllamaVramTier ||
        llamacppBaseUrl !== originalLlamacppBaseUrl ||
        llamacppModel !== originalLlamacppModel ||
        llamacppBinaryPath !== originalLlamacppBinaryPath ||
        llamacppModelPath !== originalLlamacppModelPath ||
        llamacppGpuLayers !== originalLlamacppGpuLayers ||
        llamacppCtxSize !== originalLlamacppCtxSize ||
        llamacppVramTier !== originalLlamacppVramTier ||
        JSON.stringify(ignoredMods) !== JSON.stringify(originalIgnoredMods) ||
        Object.keys(gameValues).some((key) => gameValues[key] !== originalGameValues[key])

    // The AbortController keeps StrictMode's double-mount from letting a stale response overwrite user interactions.
    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API_BASE}/settings`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json()
            })
            .then((data) => {
                setProvider(data.provider)
                setOriginalProvider(data.provider)
                setBatchSize(data.batch_size)
                setOriginalBatchSize(data.batch_size)
                setKeyStatus({
                    anthropic: data.anthropic_api_key_set,
                    openai: data.openai_api_key_set,
                    deepl: data.deepl_api_key_set,
                })
                setOllamaBaseUrl(data.ollama_base_url || "http://localhost:11434")
                setOriginalOllamaBaseUrl(data.ollama_base_url || "http://localhost:11434")
                setOllamaModel(data.ollama_model || "qwen2.5:7b")
                setOriginalOllamaModel(data.ollama_model || "qwen2.5:7b")
                setOllamaVramTier(data.ollama_vram_tier || "")
                setOriginalOllamaVramTier(data.ollama_vram_tier || "")
                setLlamacppBaseUrl(data.llamacpp_base_url || "http://localhost:8080")
                setOriginalLlamacppBaseUrl(data.llamacpp_base_url || "http://localhost:8080")
                setLlamacppModel(data.llamacpp_model || "")
                setOriginalLlamacppModel(data.llamacpp_model || "")
                setLlamacppBinaryPath(data.llamacpp_binary_path || "llama-server")
                setOriginalLlamacppBinaryPath(data.llamacpp_binary_path || "llama-server")
                setLlamacppModelPath(data.llamacpp_model_path || "")
                setOriginalLlamacppModelPath(data.llamacpp_model_path || "")
                setLlamacppGpuLayers(data.llamacpp_gpu_layers ?? -1)
                setOriginalLlamacppGpuLayers(data.llamacpp_gpu_layers ?? -1)
                setLlamacppCtxSize(data.llamacpp_ctx_size ?? 8192)
                setOriginalLlamacppCtxSize(data.llamacpp_ctx_size ?? 8192)
                setIgnoredMods(data.ignored_mods ?? [])
                setOriginalIgnoredMods(data.ignored_mods ?? [])
                const loadedGameValues = pickGameValues(data)
                setGameValues(loadedGameValues)
                setOriginalGameValues(loadedGameValues)
                setClaudeModel(data.claude_model || "claude-sonnet-5")
                setOriginalClaudeModel(data.claude_model || "claude-sonnet-5")
                setOpenaiModel(data.openai_model || "gpt-4.1")
                setOriginalOpenaiModel(data.openai_model || "gpt-4.1")
                setOllamaManaged(data.ollama_managed ?? false)
                setLlamacppVramTier(data.llamacpp_vram_tier || "")
                setOriginalLlamacppVramTier(data.llamacpp_vram_tier || "")
                setLoading(false)

                // Separate so it doesn't block page load.
                fetch(`${API_BASE}/ollama/status`, { signal: controller.signal })
                    .then((r) => r.json())
                    .then((statusData) => {
                        setOllamaStatus(statusData.status)
                        setOllamaModels(statusData.models.map((m: { name: string }) => m.name))
                        setOllamaManaged(statusData.managed ?? false)
                    })
                    .catch(() => {})

                fetch(`${API_BASE}/llamacpp/models`, { signal: controller.signal })
                    .then((r) => r.json())
                    .then((modelsData) => setLlamacppLocalModels(modelsData.models || []))
                    .catch(() => {})
            })
            .catch((err) => {
                if (err.name !== "AbortError") {
                    console.error("Failed to fetch settings:", err)
                    setLoadError(err.message)
                    setLoading(false)
                }
            })
        return () => controller.abort()
    }, [loadAttempt])

    /** Clear the load error and reload the settings. */
    const retryLoad = () => {
        setLoadError(null)
        setLoading(true)
        setLoadAttempt((n) => n + 1)
    }

    // Refetched on Retry so a backend that was down fills the Model dropdown.
    useEffect(() => {
        fetch(`${API_BASE}/models/claude`)
            .then((r) => r.json())
            .then((d) => setClaudeModels(d.models))
            .catch(() => {})
        fetch(`${API_BASE}/models/openai`)
            .then((r) => r.json())
            .then((d) => setOpenaiModels(d.models))
            .catch(() => {})
    }, [loadAttempt])

    useEffect(() => {
        if (provider !== "ollama") return
        const checkStatus = () => {
            fetch(`${API_BASE}/ollama/status`)
                .then((res) => res.json())
                .then((data) => {
                    setOllamaStatus(data.status)
                    setOllamaModels(data.models.map((m: { name: string }) => m.name))
                    setOllamaManaged(data.managed ?? false)
                })
                .catch(() => setOllamaStatus("not_installed"))
        }
        checkStatus()
        const interval = setInterval(checkStatus, 10000)
        return () => clearInterval(interval)
    }, [provider])

    // Skipped during install or download to avoid resetting state.
    useEffect(() => {
        if (provider !== "llamacpp") return
        if (llamacppInstalling || llamacppDownloading) return
        const checkStatus = () => {
            fetch(`${API_BASE}/llamacpp/status`)
                .then((res) => res.json())
                .then((data) => {
                    setLlamacppStatus(data.status)
                    setLlamacppInstalled(data.installed ?? false)
                })
                .catch(() => setLlamacppStatus("not_running"))
        }
        checkStatus()
        const interval = setInterval(checkStatus, 10000)
        return () => clearInterval(interval)
    }, [provider, llamacppBaseUrl, llamacppInstalling, llamacppDownloading])

    /** Save changed settings. Only fields that differ from their originals are sent, so unchanged keys are not overwritten. */
    const handleSave = async () => {
        setSaving(true)
        setSaveSuccess(false)
        setSaveError(null)

        const payload: Record<string, unknown> = {}
        if (provider !== originalProvider) payload.provider = provider
        if (batchSize !== originalBatchSize) payload.batch_size = batchSize
        if (apiKeys.anthropic) payload.anthropic_api_key = apiKeys.anthropic
        if (apiKeys.openai) payload.openai_api_key = apiKeys.openai
        if (apiKeys.deepl) payload.deepl_api_key = apiKeys.deepl
        if (claudeModel !== originalClaudeModel) payload.claude_model = claudeModel
        if (openaiModel !== originalOpenaiModel) payload.openai_model = openaiModel
        if (ollamaBaseUrl !== originalOllamaBaseUrl) payload.ollama_base_url = ollamaBaseUrl
        if (ollamaModel !== originalOllamaModel) payload.ollama_model = ollamaModel
        if (ollamaVramTier !== originalOllamaVramTier) payload.ollama_vram_tier = ollamaVramTier
        if (llamacppBaseUrl !== originalLlamacppBaseUrl) payload.llamacpp_base_url = llamacppBaseUrl
        if (llamacppModel !== originalLlamacppModel) payload.llamacpp_model = llamacppModel
        if (llamacppBinaryPath !== originalLlamacppBinaryPath) payload.llamacpp_binary_path = llamacppBinaryPath
        if (llamacppModelPath !== originalLlamacppModelPath) payload.llamacpp_model_path = llamacppModelPath
        if (llamacppGpuLayers !== originalLlamacppGpuLayers) payload.llamacpp_gpu_layers = llamacppGpuLayers
        if (llamacppCtxSize !== originalLlamacppCtxSize) payload.llamacpp_ctx_size = llamacppCtxSize
        if (llamacppVramTier !== originalLlamacppVramTier) payload.llamacpp_vram_tier = llamacppVramTier
        if (JSON.stringify(ignoredMods) !== JSON.stringify(originalIgnoredMods)) payload.ignored_mods = ignoredMods
        for (const [key, value] of Object.entries(gameValues)) if (value !== originalGameValues[key]) payload[key] = value

        try {
            const res = await fetch(`${API_BASE}/settings`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || "Save failed")

            setProvider(data.provider)
            setOriginalProvider(data.provider)
            setBatchSize(data.batch_size)
            setOriginalBatchSize(data.batch_size)
            setKeyStatus({
                anthropic: data.anthropic_api_key_set,
                openai: data.openai_api_key_set,
                deepl: data.deepl_api_key_set,
            })
            setApiKeys({ anthropic: "", openai: "", deepl: "" })
            setOllamaBaseUrl(data.ollama_base_url || "http://localhost:11434")
            setOriginalOllamaBaseUrl(data.ollama_base_url || "http://localhost:11434")
            setOllamaModel(data.ollama_model || "qwen2.5:7b")
            setOriginalOllamaModel(data.ollama_model || "qwen2.5:7b")
            setOllamaVramTier(data.ollama_vram_tier || "")
            setOriginalOllamaVramTier(data.ollama_vram_tier || "")
            setOllamaStatus(data.ollama_status || "not_installed")
            setLlamacppBaseUrl(data.llamacpp_base_url || "http://localhost:8080")
            setOriginalLlamacppBaseUrl(data.llamacpp_base_url || "http://localhost:8080")
            setLlamacppModel(data.llamacpp_model || "")
            setOriginalLlamacppModel(data.llamacpp_model || "")
            setLlamacppBinaryPath(data.llamacpp_binary_path || "llama-server")
            setOriginalLlamacppBinaryPath(data.llamacpp_binary_path || "llama-server")
            setLlamacppModelPath(data.llamacpp_model_path || "")
            setOriginalLlamacppModelPath(data.llamacpp_model_path || "")
            setLlamacppGpuLayers(data.llamacpp_gpu_layers ?? -1)
            setOriginalLlamacppGpuLayers(data.llamacpp_gpu_layers ?? -1)
            setLlamacppCtxSize(data.llamacpp_ctx_size ?? 8192)
            setOriginalLlamacppCtxSize(data.llamacpp_ctx_size ?? 8192)
            setOllamaManaged(data.ollama_managed ?? false)
            setLlamacppVramTier(data.llamacpp_vram_tier || "")
            setOriginalLlamacppVramTier(data.llamacpp_vram_tier || "")
            setIgnoredMods(data.ignored_mods ?? [])
            setOriginalIgnoredMods(data.ignored_mods ?? [])
            const savedGameValues = pickGameValues(data)
            setGameValues(savedGameValues)
            setOriginalGameValues(savedGameValues)
            setClaudeModel(data.claude_model || "claude-sonnet-5")
            setOriginalClaudeModel(data.claude_model || "claude-sonnet-5")
            setOpenaiModel(data.openai_model || "gpt-4.1")
            setOriginalOpenaiModel(data.openai_model || "gpt-4.1")
            setSaveSuccess(true)
            setTimeout(() => setSaveSuccess(false), 3000)
        } catch (err) {
            console.error("Failed to save settings:", err)
            setSaveError(`Could not save settings: ${err instanceof Error ? err.message : String(err)}`)
        } finally {
            setSaving(false)
        }
    }

    const handleVramTierSelect = (tier: (typeof VRAM_TIERS)[0]) => {
        if (ollamaVramTier === tier.tier) {
            setOllamaVramTier("")
            setOllamaModel("")
        } else {
            setOllamaVramTier(tier.tier)
            setOllamaModel(tier.model)
        }
    }

    const handleOllamaInstall = async () => {
        setOllamaInstalling(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/install`, { method: "POST" })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail)
        } catch (err) {
            console.error("Failed to install Ollama:", err)
        } finally {
            setOllamaInstalling(false)
        }
    }

    const handleOllamaPull = async (modelName: string) => {
        setOllamaPulling(true)
        setOllamaPullProgress(null)
        try {
            const res = await fetch(`${API_BASE}/ollama/pull`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: modelName }),
            })
            const reader = res.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) return

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                const text = decoder.decode(value)
                for (const line of text.split("\n")) {
                    if (line.startsWith("data: ")) {
                        try {
                            const progress = JSON.parse(line.slice(6))
                            setOllamaPullProgress(progress)
                            if (progress.status === "done") break
                        } catch {
                            /* skip malformed lines */
                        }
                    }
                }
            }
            fetch(`${API_BASE}/ollama/status`)
                .then((r) => r.json())
                .then((data) => {
                    setOllamaStatus(data.status)
                    setOllamaModels(data.models.map((m: { name: string }) => m.name))
                })
                .catch(() => {})
        } catch (err) {
            console.error("Failed to pull model:", err)
        } finally {
            setOllamaPulling(false)
            setOllamaPullProgress(null)
        }
    }

    const handleOllamaStart = async () => {
        setOllamaStarting(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/start`, { method: "POST" })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail)
            setOllamaManaged(data.managed)
            const statusRes = await fetch(`${API_BASE}/ollama/status`)
            const statusData = await statusRes.json()
            setOllamaStatus(statusData.status)
            setOllamaManaged(statusData.managed ?? false)
            setOllamaModels(statusData.models.map((m: { name: string }) => m.name))
        } catch (err) {
            console.error("Failed to start Ollama:", err)
        } finally {
            setOllamaStarting(false)
        }
    }

    const handleOllamaStop = async () => {
        setOllamaStopping(true)
        try {
            const res = await fetch(`${API_BASE}/ollama/stop`, { method: "POST" })
            if (!res.ok) {
                const data = await res.json()
                throw new Error(data.detail)
            }
            setOllamaManaged(false)
            setOllamaStatus("stopped")
        } catch (err) {
            console.error("Failed to stop Ollama:", err)
        } finally {
            setOllamaStopping(false)
        }
    }

    const refreshLlamacppModels = () => {
        fetch(`${API_BASE}/llamacpp/models`)
            .then((r) => r.json())
            .then((data) => setLlamacppLocalModels(data.models || []))
            .catch(() => {})
    }

    const handleGgufTierSelect = (tier: (typeof GGUF_TIERS)[0]) => {
        if (llamacppVramTier === tier.tier) {
            setLlamacppVramTier("")
            setLlamacppModel("")
        } else {
            setLlamacppVramTier(tier.tier)
            setLlamacppModel(tier.model)
            // Reuse the model path if this GGUF is already downloaded.
            const local = llamacppLocalModels.find((m) => m.name === tier.filename)
            if (local) {
                setLlamacppModelPath(local.path)
                setOriginalLlamacppModelPath(local.path)
                setOriginalLlamacppModel(tier.model)
                setOriginalLlamacppVramTier(tier.tier)
                fetch(`${API_BASE}/settings`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        llamacpp_model_path: local.path,
                        llamacpp_model: tier.model,
                        llamacpp_vram_tier: tier.tier,
                    }),
                }).catch(() => {})
            }
        }
    }

    const handleGgufDownload = async (tier: (typeof GGUF_TIERS)[0]) => {
        setLlamacppDownloading(true)
        setLlamacppDownloadProgress(null)
        try {
            const res = await fetch(`${API_BASE}/llamacpp/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: tier.url, filename: tier.filename }),
            })

            const reader = res.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) {
                console.error("GGUF download: no reader available")
                return
            }

            let buffer = ""
            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split("\n")
                buffer = lines.pop() || "" // keep incomplete last line in buffer
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const progress = JSON.parse(line.slice(6))
                            setLlamacppDownloadProgress(progress)
                            if (progress.status === "done" && progress.path) {
                                setLlamacppModelPath(progress.path)
                                setOriginalLlamacppModelPath(progress.path)
                                fetch(`${API_BASE}/settings`, {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({
                                        llamacpp_model_path: progress.path,
                                        llamacpp_model: tier.model,
                                        llamacpp_vram_tier: tier.tier,
                                    }),
                                }).catch(() => {})
                                setOriginalLlamacppModel(tier.model)
                                setOriginalLlamacppVramTier(tier.tier)
                            }
                            if (progress.status === "error") {
                                console.error("GGUF download error:", progress.message)
                            }
                        } catch {
                            /* skip malformed lines */
                        }
                    }
                }
            }
            refreshLlamacppModels()
        } catch (err) {
            console.error("Failed to download GGUF:", err)
        } finally {
            setLlamacppDownloading(false)
            setLlamacppDownloadProgress(null)
        }
    }

    const handleGgufDelete = async (filename: string) => {
        try {
            const res = await fetch(`${API_BASE}/llamacpp/models/${encodeURIComponent(filename)}`, { method: "DELETE" })
            if (!res.ok) return
            refreshLlamacppModels()
            const deleted = llamacppLocalModels.find((m) => m.name === filename)
            if (deleted && llamacppModelPath === deleted.path) {
                setLlamacppModelPath("")
            }
        } catch (err) {
            console.error("Failed to delete model:", err)
        }
    }

    const handleLlamacppInstall = async (backend: string) => {
        setLlamacppInstalling(true)
        setLlamacppInstallProgress(null)
        try {
            const res = await fetch(`${API_BASE}/llamacpp/install`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ backend }),
            })
            const reader = res.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) return

            let buffer = ""
            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split("\n")
                buffer = lines.pop() || ""
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const progress = JSON.parse(line.slice(6))
                            setLlamacppInstallProgress(progress)
                            if (progress.status === "done") {
                                setLlamacppInstalled(true)
                                if (progress.binary_path) {
                                    setLlamacppBinaryPath(progress.binary_path)
                                    setOriginalLlamacppBinaryPath(progress.binary_path)
                                }
                            }
                        } catch {
                            /* skip */
                        }
                    }
                }
            }
        } catch (err) {
            console.error("Failed to install llama-server:", err)
        } finally {
            setLlamacppInstalling(false)
            setLlamacppInstallProgress(null)
        }
    }

    const isModelDownloaded = ollamaModels.some((m) => m === ollamaModel || m === ollamaModel + ":latest" || m + ":latest" === ollamaModel)

    // The user overrode the model when it differs from the VRAM tier default.
    const tierDefault = VRAM_TIERS.find((t) => t.tier === ollamaVramTier)?.model || ""
    const isModelOverride = ollamaModel !== "" && ollamaModel !== tierDefault

    const ollamaTone = ollamaStatus === "running" ? "success" : ollamaStatus === "stopped" ? "warning" : ollamaStatus === "unknown" ? "dim" : "danger"
    // Ready once installed with a model, even before the server starts.
    const llamacppTone = llamacppStatus === "running" || (llamacppInstalled && llamacppModelPath) ? "success" : llamacppStatus === "unknown" ? "dim" : "danger"
    const statusLabel = ollamaStatus === "running" ? "Running" : ollamaStatus === "stopped" ? "Stopped (not running)" : ollamaStatus === "unknown" ? "Checking..." : "Not Installed"

    if (loading) return <LoadingState message="Loading settings..." />
    if (loadError) {
        return (
            <ErrorState
                title="Could not load settings"
                message={`${loadError}. Nothing has been changed. Check that the backend is running, then retry.`}
                action={{ label: "Retry", onClick: retryLoad }}
            />
        )
    }

    return (
        <div className="settings-view">
            <PageHeader title="Settings" meta={<p>API Keys and Provider Configuration</p>} />

            <Panel
                className="settings-panel"
                title="System Prompt Preview"
                help={`View the system prompt sent for ${getGame(gameId)?.displayName ?? gameId} translations. Uses that game's base glossary and translation settings.`}
            >
                <div className="settings-inline-row">
                    <label className="field-label" htmlFor={`${fieldId}-prompt-lang`}>
                        Source Language
                    </label>
                    <select id={`${fieldId}-prompt-lang`} value={promptSourceLang} onChange={(e) => setPromptSourceLang(e.target.value)} className="select select-auto">
                        <option value="Chinese">Chinese</option>
                        <option value="Korean">Korean</option>
                        <option value="Japanese">Japanese</option>
                    </select>
                    <button
                        className="btn btn-outline"
                        onClick={async () => {
                            // A loaded prompt turns the button into Unload, which closes it.
                            if (systemPrompt) {
                                setSystemPrompt("")
                                return
                            }
                            setPromptLoading(true)
                            try {
                                const res = await gameApi(gameId).get(`/translate/system-prompt?source_lang=${encodeURIComponent(promptSourceLang)}`)
                                const data = await res.json()
                                setSystemPrompt(data.system_prompt || "")
                            } catch (err) {
                                console.error("Failed to fetch system prompt:", err)
                                setSystemPrompt("Error fetching system prompt.")
                            } finally {
                                setPromptLoading(false)
                            }
                        }}
                        disabled={promptLoading}
                    >
                        {promptLoading ? "Loading..." : systemPrompt ? "Unload Prompt" : "Load Prompt"}
                    </button>
                </div>
                {systemPrompt && <pre className="code-block">{systemPrompt}</pre>}
            </Panel>

            <Panel className="settings-panel" title="Translation Provider">
                <div className="provider-cards">
                    {PROVIDERS.map((p) => (
                        <div key={p.id} className={`provider-card ${provider === p.id ? "active" : ""}`} onClick={() => setProvider(p.id)}>
                            <div className="provider-card-title">{p.label}</div>
                            <div className="provider-card-description">{p.description}</div>
                        </div>
                    ))}
                </div>
            </Panel>

            {(provider === "claude" || provider === "openai") && (
                <Panel className="settings-panel" title="Model">
                    <select
                        value={provider === "claude" ? claudeModel : openaiModel}
                        onChange={(e) => (provider === "claude" ? setClaudeModel(e.target.value) : setOpenaiModel(e.target.value))}
                        aria-label="Model"
                        className="select"
                    >
                        {(provider === "claude" ? claudeModels : openaiModels).map((m) => (
                            <option key={m.id} value={m.id}>
                                {m.label} — ${m.input_per_mtok} / ${m.output_per_mtok} per MTok (in/out)
                            </option>
                        ))}
                    </select>
                </Panel>
            )}

            {provider === "manual" && (
                <Panel className="settings-panel" title="Manual Translation Mode">
                    <div className="settings-prose">
                        <p>
                            Press <strong>Translate (Manual)</strong> on a mod to step through its missing strings one at a time, with matching glossary terms and the paired name or description
                            alongside. <strong>Re-Translate All</strong> steps through every string instead.
                        </p>
                        <p>Each save is stored like a table edit and marked &quot;manual&quot; in the Mode column. Run Sync Changes afterwards to write them into the mod.</p>
                        <p>This mode has no API cost and needs no API keys.</p>
                    </div>
                </Panel>
            )}

            {provider === "ollama" && (
                <Panel className="settings-panel" title="Ollama Configuration">
                    <div className="status-row">
                        <span className={`status-dot status-dot-${ollamaTone}`} aria-hidden="true" />
                        <span className="status-label">{statusLabel}</span>
                        {ollamaStatus === "stopped" && (
                            <button className="btn btn-primary btn-sm status-action" disabled={ollamaStarting} onClick={handleOllamaStart}>
                                <FaPlay />
                                {ollamaStarting ? "Starting..." : "Start"}
                            </button>
                        )}
                        {ollamaStatus === "running" && ollamaManaged && (
                            <button className="btn btn-danger btn-sm status-action" disabled={ollamaStopping} onClick={handleOllamaStop}>
                                <FaStop />
                                {ollamaStopping ? "Stopping..." : "Stop"}
                            </button>
                        )}
                        {ollamaStatus === "running" && !ollamaManaged && <span className="note status-action">Started externally</span>}
                    </div>

                    {ollamaStatus === "not_installed" && (
                        <div className="settings-block">
                            <p className="settings-block-help">Ollama is not installed. Click below to download and install it automatically.</p>
                            <button className="btn btn-primary" disabled={ollamaInstalling} onClick={handleOllamaInstall}>
                                <FaDownload />
                                {ollamaInstalling ? "Downloading installer..." : "Install Ollama"}
                            </button>
                        </div>
                    )}

                    <div className="settings-block">
                        <h4 className="settings-subheading">GPU VRAM Tier</h4>
                        <p className="settings-block-help">Select your GPU's VRAM to get the best model recommendation for translation quality.</p>
                        <div className="vram-tier-cards">
                            {VRAM_TIERS.map((t) => (
                                <div key={t.tier} className={`vram-tier-card ${ollamaVramTier === t.tier ? "active" : ""}`} onClick={() => handleVramTierSelect(t)}>
                                    <div className="tier-card-title">{t.label}</div>
                                    <div className="tier-card-model">{t.model}</div>
                                    <div className="tier-card-meta">{t.description}</div>
                                    <div className="tier-card-meta">{t.size} download</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {ollamaVramTier && (
                        <div className="settings-block">
                            <div className="settings-selected-row">
                                <span className="settings-selected-label">
                                    Selected model: <strong className="accent-text">{ollamaModel}</strong>
                                </span>
                                {ollamaStatus === "running" && (
                                    <span className={`key-status ${isModelDownloaded ? "configured" : "missing"}`}>
                                        {isModelDownloaded ? (
                                            <>
                                                <FaCheck /> Downloaded
                                            </>
                                        ) : (
                                            <>
                                                <FaExclamationTriangle /> Not downloaded
                                            </>
                                        )}
                                    </span>
                                )}
                            </div>

                            {ollamaStatus === "running" && !isModelDownloaded && !ollamaPulling && (
                                <button className="btn btn-primary" onClick={() => handleOllamaPull(ollamaModel)}>
                                    <FaDownload />
                                    Download Model
                                </button>
                            )}

                            {ollamaPulling && ollamaPullProgress && (
                                <div className="settings-subrow">
                                    <div className="progress-status">{ollamaPullProgress.status}...</div>
                                    {(ollamaPullProgress.total ?? 0) > 0 && <DownloadProgress completed={ollamaPullProgress.completed || 0} total={ollamaPullProgress.total ?? 0} />}
                                </div>
                            )}
                            {ollamaPulling && !ollamaPullProgress && <div className="progress-status">Starting download...</div>}
                        </div>
                    )}

                    <p className="note">Smaller models may produce lower quality translations. Consider reducing batch size for models under 14B parameters.</p>

                    <div>
                        <button type="button" className="disclosure-btn" aria-expanded={showOllamaAdvanced} onClick={() => setShowOllamaAdvanced(!showOllamaAdvanced)}>
                            {showOllamaAdvanced ? <FaChevronDown /> : <FaChevronRight />}
                            Advanced Settings
                        </button>
                        {showOllamaAdvanced && (
                            <div className="settings-advanced">
                                <Field label="Ollama URL" htmlFor={`${fieldId}-ollama-url`}>
                                    <input
                                        id={`${fieldId}-ollama-url`}
                                        type="text"
                                        className="input input-medium"
                                        value={ollamaBaseUrl}
                                        onChange={(e) => setOllamaBaseUrl(e.target.value)}
                                        placeholder="http://localhost:11434"
                                    />
                                </Field>
                                <Field label="Model (override)" htmlFor={`${fieldId}-ollama-override`}>
                                    <p className="field-help">Use an installed model instead of the recommended one above.</p>
                                    {(() => {
                                        const overrideModels = ollamaModels.filter((m) => !VRAM_TIERS.some((t) => t.model === m))
                                        return overrideModels.length > 0 ? (
                                            <select
                                                id={`${fieldId}-ollama-override`}
                                                value={isModelOverride ? ollamaModel : ""}
                                                className="select input-medium"
                                                onChange={(e) => {
                                                    const val = e.target.value
                                                    if (val === "") {
                                                        const tierModel = VRAM_TIERS.find((t) => t.tier === ollamaVramTier)?.model || ""
                                                        setOllamaModel(tierModel)
                                                    } else {
                                                        setOllamaModel(val)
                                                    }
                                                }}
                                            >
                                                <option value="">None (use recommended)</option>
                                                {overrideModels.map((m) => (
                                                    <option key={m} value={m}>
                                                        {m}
                                                    </option>
                                                ))}
                                            </select>
                                        ) : (
                                            <span className="note">{ollamaStatus === "running" ? "No other models installed" : "Ollama not running"}</span>
                                        )
                                    })()}
                                </Field>
                            </div>
                        )}
                    </div>
                </Panel>
            )}

            {provider === "llamacpp" && (
                <Panel className="settings-panel" title="llama.cpp Configuration">
                    <div className="status-row">
                        <span className={`status-dot status-dot-${llamacppTone}`} aria-hidden="true" />
                        <span className="status-label">
                            {llamacppStatus === "running" ? "Running" : llamacppInstalled && llamacppModelPath ? "Ready" : llamacppStatus === "unknown" ? "Checking..." : "Not Configured"}
                        </span>
                        {llamacppInstalled && llamacppModelPath && llamacppStatus !== "running" && <span className="note status-action">Server starts automatically when translating</span>}
                    </div>

                    {!llamacppInstalled && !llamacppInstalling && llamacppStatus !== "running" && (
                        <div className="settings-block">
                            <h4 className="settings-subheading">Install llama-server</h4>
                            <p className="settings-block-help">Select your GPU type to download the correct llama-server build.</p>
                            <div className="settings-button-row">
                                <button className="btn btn-primary" onClick={() => handleLlamacppInstall("cuda-13")}>
                                    <FaDownload />
                                    NVIDIA RTX 40/50 series
                                </button>
                                <button className="btn btn-outline" onClick={() => handleLlamacppInstall("cuda-12")}>
                                    <FaDownload />
                                    NVIDIA RTX 20/30 series
                                </button>
                                <button className="btn btn-outline" onClick={() => handleLlamacppInstall("vulkan")}>
                                    <FaDownload />
                                    Any GPU (Vulkan)
                                </button>
                                <button className="btn btn-outline" onClick={() => handleLlamacppInstall("cpu")}>
                                    <FaDownload />
                                    CPU Only
                                </button>
                            </div>
                        </div>
                    )}
                    {llamacppInstalling && (
                        <div className="settings-block">
                            <div className="progress-status">
                                {llamacppInstallProgress?.status === "fetching_release" && "Finding latest release..."}
                                {llamacppInstallProgress?.status === "downloading" && `Downloading ${llamacppInstallProgress.file || ""}...`}
                                {llamacppInstallProgress?.status === "extracting" && "Extracting..."}
                                {!llamacppInstallProgress && "Starting install..."}
                            </div>
                            {llamacppInstallProgress && (llamacppInstallProgress.total ?? 0) > 0 && (
                                <DownloadProgress completed={llamacppInstallProgress.completed || 0} total={llamacppInstallProgress.total ?? 0} />
                            )}
                        </div>
                    )}

                    <div className="settings-block">
                        <h4 className="settings-subheading">GPU VRAM Tier</h4>
                        <p className="settings-block-help">Select your GPU's VRAM to get the best model recommendation. The model will be downloaded automatically.</p>
                        <div className="vram-tier-cards">
                            {GGUF_TIERS.map((t) => (
                                <div key={t.tier} className={`vram-tier-card ${llamacppVramTier === t.tier ? "active" : ""}`} onClick={() => handleGgufTierSelect(t)}>
                                    <div className="tier-card-title">{t.label}</div>
                                    <div className="tier-card-model">{t.model}</div>
                                    <div className="tier-card-meta">{t.description}</div>
                                    <div className="tier-card-meta">{t.size} download</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {llamacppVramTier &&
                        (() => {
                            const selectedTier = GGUF_TIERS.find((t) => t.tier === llamacppVramTier)!
                            const isDownloaded = llamacppLocalModels.some((m) => m.name === selectedTier.filename)
                            return (
                                <div className="settings-block">
                                    <div className="settings-selected-row">
                                        <span className="settings-selected-label">
                                            Selected model: <strong className="accent-text">{selectedTier.filename}</strong>
                                        </span>
                                        <span className={`key-status ${isDownloaded ? "configured" : "missing"}`}>
                                            {isDownloaded ? (
                                                <>
                                                    <FaCheck /> Downloaded
                                                </>
                                            ) : (
                                                <>
                                                    <FaExclamationTriangle /> Not downloaded
                                                </>
                                            )}
                                        </span>
                                    </div>

                                    {!isDownloaded && !llamacppDownloading && (
                                        <button className="btn btn-primary" onClick={() => handleGgufDownload(selectedTier)}>
                                            <FaDownload />
                                            Download Model ({selectedTier.size})
                                        </button>
                                    )}

                                    {llamacppDownloading && llamacppDownloadProgress && (
                                        <div className="settings-subrow">
                                            <div className="progress-status">{llamacppDownloadProgress.status === "connecting" ? "Connecting to HuggingFace..." : "Downloading..."}</div>
                                            {(llamacppDownloadProgress.total ?? 0) > 0 && (
                                                <DownloadProgress completed={llamacppDownloadProgress.completed || 0} total={llamacppDownloadProgress.total ?? 0} />
                                            )}
                                        </div>
                                    )}
                                    {llamacppDownloading && !llamacppDownloadProgress && <div className="progress-status">Connecting...</div>}

                                    {isDownloaded && (
                                        <button type="button" className="btn-link settings-subrow" onClick={() => handleGgufDelete(selectedTier.filename)}>
                                            Delete downloaded model
                                        </button>
                                    )}
                                </div>
                            )
                        })()}

                    <p className="note">Smaller models may produce lower quality translations. Consider reducing batch size for models under 14B parameters.</p>

                    <div>
                        <button type="button" className="disclosure-btn" aria-expanded={showLlamacppAdvanced} onClick={() => setShowLlamacppAdvanced(!showLlamacppAdvanced)}>
                            {showLlamacppAdvanced ? <FaChevronDown /> : <FaChevronRight />}
                            Advanced Settings
                        </button>
                        {showLlamacppAdvanced && (
                            <div className="settings-advanced">
                                <Field label="Model Path (override)" htmlFor={`${fieldId}-llamacpp-model-path`}>
                                    <p className="field-help">Auto-filled when you download a model. Override to use a different GGUF file.</p>
                                    <input
                                        id={`${fieldId}-llamacpp-model-path`}
                                        type="text"
                                        className="input input-wide"
                                        value={llamacppModelPath}
                                        onChange={(e) => setLlamacppModelPath(e.target.value)}
                                        placeholder="Auto-filled on download"
                                    />
                                </Field>
                                <div className="settings-field-row">
                                    <Field label="GPU Layers" htmlFor={`${fieldId}-llamacpp-gpu-layers`}>
                                        <p className="field-help">-1 = offload all layers to GPU</p>
                                        <input
                                            id={`${fieldId}-llamacpp-gpu-layers`}
                                            type="number"
                                            className="input input-number"
                                            value={llamacppGpuLayers}
                                            onChange={(e) => {
                                                const val = parseInt(e.target.value, 10)
                                                if (!isNaN(val)) setLlamacppGpuLayers(val)
                                            }}
                                        />
                                    </Field>
                                    <Field label="Context Size" htmlFor={`${fieldId}-llamacpp-ctx-size`}>
                                        <p className="field-help">Tokens for prompt + response</p>
                                        <input
                                            id={`${fieldId}-llamacpp-ctx-size`}
                                            type="number"
                                            min={512}
                                            step={1024}
                                            className="input input-number"
                                            value={llamacppCtxSize}
                                            onChange={(e) => {
                                                const val = parseInt(e.target.value, 10)
                                                if (!isNaN(val)) setLlamacppCtxSize(val)
                                            }}
                                        />
                                    </Field>
                                </div>
                                <Field label="Server URL" htmlFor={`${fieldId}-llamacpp-url`}>
                                    <input
                                        id={`${fieldId}-llamacpp-url`}
                                        type="text"
                                        className="input input-medium"
                                        value={llamacppBaseUrl}
                                        onChange={(e) => setLlamacppBaseUrl(e.target.value)}
                                        placeholder="http://localhost:8080"
                                    />
                                </Field>
                                <Field label="Binary Path" htmlFor={`${fieldId}-llamacpp-binary`}>
                                    <p className="field-help">Path to the llama-server binary. Default assumes it is on PATH.</p>
                                    <input
                                        id={`${fieldId}-llamacpp-binary`}
                                        type="text"
                                        className="input input-wide"
                                        value={llamacppBinaryPath}
                                        onChange={(e) => setLlamacppBinaryPath(e.target.value)}
                                        placeholder="llama-server"
                                    />
                                </Field>
                                <Field label="Display Name" htmlFor={`${fieldId}-llamacpp-display-name`}>
                                    <p className="field-help">Label shown in the UI during translation. Auto-filled from tier selection.</p>
                                    <input
                                        id={`${fieldId}-llamacpp-display-name`}
                                        type="text"
                                        className="input input-medium"
                                        value={llamacppModel}
                                        onChange={(e) => setLlamacppModel(e.target.value)}
                                        placeholder="e.g. Qwen2.5-14B-Instruct"
                                    />
                                </Field>
                            </div>
                        )}
                    </div>
                </Panel>
            )}

            {provider !== "manual" && provider !== "ollama" && provider !== "llamacpp" && (
                <Panel className="settings-panel" title="API Keys">
                    {PROVIDERS.filter((p) => p.keyField !== null).map((p) => {
                        const field = p.keyField!
                        const isSelected = provider === p.id
                        const status = keyStatus[field]
                        const isConfigured = status !== ""

                        return (
                            <div key={field} className={`key-row${isSelected ? " selected" : ""}`}>
                                <div className="key-row-header">
                                    <label className="field-label" htmlFor={`${fieldId}-key-${field}`}>
                                        {p.label} API Key
                                    </label>
                                    <span className={`key-status ${isConfigured ? "configured" : "missing"}`}>
                                        {isConfigured ? (
                                            <>
                                                <FaCheck /> {status}
                                            </>
                                        ) : (
                                            <>
                                                <FaExclamationTriangle /> Not configured
                                            </>
                                        )}
                                    </span>
                                </div>
                                <div className="key-input-wrapper">
                                    <input
                                        id={`${fieldId}-key-${field}`}
                                        type={keyVisible[field] ? "text" : "password"}
                                        value={apiKeys[field]}
                                        onChange={(e) => setApiKeys((prev) => ({ ...prev, [field]: e.target.value }))}
                                        placeholder={isConfigured ? "Enter new key to update..." : "Enter API key..."}
                                    />
                                    <button
                                        className="key-toggle-btn"
                                        onClick={() => setKeyVisible((prev) => ({ ...prev, [field]: !prev[field] }))}
                                        title={keyVisible[field] ? "Hide" : "Show"}
                                        type="button"
                                    >
                                        {keyVisible[field] ? <FaEyeSlash /> : <FaEye />}
                                    </button>
                                </div>
                            </div>
                        )
                    })}
                </Panel>
            )}

            <Panel className="settings-panel" title="Batch Size" help="Number of strings sent per API request. Larger batches are more cost-efficient but may hit token limits.">
                <input
                    type="number"
                    min={1}
                    max={500}
                    aria-label="Batch size"
                    className="input input-number"
                    value={batchSize}
                    onChange={(e) => {
                        const val = parseInt(e.target.value, 10)
                        if (!isNaN(val)) setBatchSize(val)
                    }}
                />
            </Panel>

            <Panel
                className="settings-panel"
                title="Ignored Mods"
                help="Workshop mod IDs listed here will be hidden from the dashboard. Useful for system mods, English-only mods, or mods you don't need to translate."
            >
                <div className="settings-inline-row">
                    <input
                        type="text"
                        aria-label="Workshop mod ID"
                        className="input"
                        placeholder="Workshop mod ID"
                        value={newIgnoredMod}
                        onChange={(e) => setNewIgnoredMod(e.target.value.trim())}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && newIgnoredMod && !ignoredMods.includes(newIgnoredMod)) {
                                setIgnoredMods([...ignoredMods, newIgnoredMod])
                                setNewIgnoredMod("")
                            }
                        }}
                    />
                    <button
                        className="btn btn-primary"
                        disabled={!newIgnoredMod || ignoredMods.includes(newIgnoredMod)}
                        onClick={() => {
                            if (newIgnoredMod && !ignoredMods.includes(newIgnoredMod)) {
                                setIgnoredMods([...ignoredMods, newIgnoredMod])
                                setNewIgnoredMod("")
                            }
                        }}
                    >
                        Add
                    </button>
                </div>
                {ignoredMods.length > 0 && (
                    <div className="chip-list">
                        {ignoredMods.map((id) => (
                            <span key={id} className="chip">
                                {id}
                                <button type="button" className="chip-remove" aria-label={`Remove ${id}`} title="Remove" onClick={() => setIgnoredMods(ignoredMods.filter((m) => m !== id))}>
                                    <FaTimes />
                                </button>
                            </span>
                        ))}
                    </div>
                )}
            </Panel>

            {listGames().map((game) => {
                const slot = game.settingsPanel
                if (!slot) return null
                const values = Object.fromEntries(slot.keys.map((key) => [key, gameValues[key] ?? ""]))
                return <slot.Panel key={game.id} values={values} onChange={setGameValue} onSaved={markGameValueSaved} fieldId={fieldId} />
            })}

            {saveError && (
                <Banner tone="error" onDismiss={() => setSaveError(null)}>
                    {saveError}
                </Banner>
            )}
            <div className="settings-save-row">
                <button className="btn btn-primary" disabled={!isChanged || saving} onClick={handleSave}>
                    {saving ? "Saving..." : "Save Settings"}
                </button>
                {saveSuccess && <span className="text-success">Settings saved successfully</span>}
            </div>
        </div>
    )
}

export default SettingsPage
