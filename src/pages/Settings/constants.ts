/** One progress event from the Ollama pull and llama.cpp download and install streams. */
export interface StreamProgress {
    status: string
    completed?: number
    total?: number
    file?: string
    path?: string
    binary_path?: string
    message?: string
}

/** The providers that need an API key, by the key's short name. */
export type KeyField = "anthropic" | "openai" | "deepl"

/** Available translation providers, mapping a backend provider id to its label, description, and API key field (`null` when no credentials are needed). */
export const PROVIDERS: { id: string; label: string; description: string; keyField: KeyField | null }[] = [
    { id: "claude", label: "Claude", description: "Anthropic", keyField: "anthropic" },
    { id: "openai", label: "OpenAI", description: "OpenAI", keyField: "openai" },
    { id: "deepl", label: "DeepL", description: "Neural Machine Translation", keyField: "deepl" },
    { id: "ollama", label: "Ollama (Local)", description: "Free local AI — no API key needed", keyField: null },
    { id: "llamacpp", label: "llama.cpp (Local)", description: "Direct llama-server connection", keyField: null },
    { id: "manual", label: "Manual", description: "Translate by hand in the app", keyField: null },
]

/** VRAM tier to recommended Ollama model mapping. */
export const VRAM_TIERS = [
    { tier: "4-6gb", label: "4-6 GB", model: "gemma3:4b", description: "Google multilingual small", size: "3.3 GB" },
    { tier: "8gb", label: "8 GB", model: "qwen2.5:7b", description: "Alibaba, excellent CJK", size: "4.7 GB" },
    { tier: "12gb", label: "12 GB", model: "qwen2.5:14b", description: "Larger Qwen, better quality", size: "9.0 GB" },
    { tier: "16gb", label: "16 GB", model: "mistral-small:22b", description: "Strong reasoning", size: "13 GB" },
    { tier: "24gb+", label: "24 GB+", model: "qwen2.5:32b", description: "Near-API quality", size: "20 GB" },
]

/** VRAM tier to recommended GGUF model mapping for llama.cpp. Single-file quantizations from bartowski. */
export const GGUF_TIERS = [
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

export type GgufTier = (typeof GGUF_TIERS)[number]
