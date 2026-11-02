import React, { useState } from "react"
import { FaCheck, FaChevronDown, FaChevronRight, FaDownload, FaExclamationTriangle } from "react-icons/fa"
import DownloadProgress from "@/components/ui/DownloadProgress"
import Field from "@/components/ui/Field"
import Panel from "@/components/ui/Panel"
import { GGUF_TIERS } from "@/pages/Settings/constants"
import type { LlamacppState } from "@/pages/Settings/useLlamacpp"
import type { SettingsForm } from "@/pages/Settings/useSettingsForm"

/** Props for LlamacppPanel. */
interface LlamacppPanelProps {
    llamacpp: LlamacppState
    form: SettingsForm
    update: (patch: Partial<SettingsForm>) => void
    /** Prefix for field ids, unique to the Settings page. */
    fieldId: string
}

/** llama-server builds offered for install, the first one highlighted as the usual pick. */
const BUILDS = [
    { backend: "cuda-13", label: "NVIDIA RTX 40/50 series" },
    { backend: "cuda-12", label: "NVIDIA RTX 20/30 series" },
    { backend: "vulkan", label: "Any GPU (Vulkan)" },
    { backend: "cpu", label: "CPU Only" },
]

/**
 * Read a whole number from a number input, ignoring a half-typed value.
 *
 * @param value The input's text.
 * @param apply Called with the number when it parses.
 */
function onInteger(value: string, apply: (n: number) => void) {
    const n = parseInt(value, 10)
    if (!isNaN(n)) apply(n)
}

/**
 * Settings panel for the llama.cpp provider: server status, llama-server install, the GGUF tier picker and download, and the advanced fields.
 *
 * @param props The llama.cpp state, the Settings form and its update, and the field id prefix.
 * @returns The llama.cpp configuration panel.
 */
const LlamacppPanel: React.FC<LlamacppPanelProps> = ({ llamacpp, form, update, fieldId }) => {
    const [showAdvanced, setShowAdvanced] = useState(false)
    const { status, installed, installProgress, downloadProgress } = llamacpp
    // Ready once installed with a model, even before the server starts.
    const ready = installed && form.llamacpp_model_path !== ""
    const tone = status === "running" || ready ? "success" : status === "unknown" ? "dim" : "danger"
    const statusLabel = status === "running" ? "Running" : ready ? "Ready" : status === "unknown" ? "Checking..." : "Not Configured"
    const selectedTier = GGUF_TIERS.find((t) => t.tier === form.llamacpp_vram_tier)
    const isDownloaded = selectedTier !== undefined && llamacpp.localModels.some((m) => m.name === selectedTier.filename)

    return (
        <Panel className="settings-panel" title="llama.cpp Configuration">
            <div className="status-row">
                <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />
                <span className="status-label">{statusLabel}</span>
                {ready && status !== "running" && <span className="note status-action">Server starts automatically when translating</span>}
            </div>

            {!installed && !llamacpp.installing && status !== "running" && (
                <div className="settings-block">
                    <h4 className="settings-subheading">Install llama-server</h4>
                    <p className="settings-block-help">Select your GPU type to download the correct llama-server build.</p>
                    <div className="settings-button-row">
                        {BUILDS.map((build, i) => (
                            <button key={build.backend} className={`btn ${i === 0 ? "btn-primary" : "btn-outline"}`} onClick={() => llamacpp.install(build.backend)}>
                                <FaDownload />
                                {build.label}
                            </button>
                        ))}
                    </div>
                </div>
            )}
            {llamacpp.installing && (
                <div className="settings-block">
                    <div className="progress-status">
                        {installProgress?.status === "fetching_release" && "Finding latest release..."}
                        {installProgress?.status === "downloading" && `Downloading ${installProgress.file || ""}...`}
                        {installProgress?.status === "extracting" && "Extracting..."}
                        {!installProgress && "Starting install..."}
                    </div>
                    {installProgress && (installProgress.total ?? 0) > 0 && <DownloadProgress completed={installProgress.completed || 0} total={installProgress.total ?? 0} />}
                </div>
            )}

            <div className="settings-block">
                <h4 className="settings-subheading">GPU VRAM Tier</h4>
                <p className="settings-block-help">Select your GPU's VRAM to get the best model recommendation. The model will be downloaded automatically.</p>
                <div className="vram-tier-cards">
                    {GGUF_TIERS.map((t) => (
                        <div key={t.tier} className={`vram-tier-card ${form.llamacpp_vram_tier === t.tier ? "active" : ""}`} onClick={() => llamacpp.selectTier(t)}>
                            <div className="tier-card-title">{t.label}</div>
                            <div className="tier-card-model">{t.model}</div>
                            <div className="tier-card-meta">{t.description}</div>
                            <div className="tier-card-meta">{t.size} download</div>
                        </div>
                    ))}
                </div>
            </div>

            {selectedTier && (
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

                    {!isDownloaded && !llamacpp.downloading && (
                        <button className="btn btn-primary" onClick={() => llamacpp.download(selectedTier)}>
                            <FaDownload />
                            Download Model ({selectedTier.size})
                        </button>
                    )}

                    {llamacpp.downloading && downloadProgress && (
                        <div className="settings-subrow">
                            <div className="progress-status">{downloadProgress.status === "connecting" ? "Connecting to HuggingFace..." : "Downloading..."}</div>
                            {(downloadProgress.total ?? 0) > 0 && <DownloadProgress completed={downloadProgress.completed || 0} total={downloadProgress.total ?? 0} />}
                        </div>
                    )}
                    {llamacpp.downloading && !downloadProgress && <div className="progress-status">Connecting...</div>}

                    {isDownloaded && (
                        <button type="button" className="btn-link settings-subrow" onClick={() => llamacpp.deleteModel(selectedTier.filename)}>
                            Delete downloaded model
                        </button>
                    )}
                </div>
            )}

            <p className="note">Smaller models may produce lower quality translations. Consider reducing batch size for models under 14B parameters.</p>

            <div>
                <button type="button" className="disclosure-btn" aria-expanded={showAdvanced} onClick={() => setShowAdvanced(!showAdvanced)}>
                    {showAdvanced ? <FaChevronDown /> : <FaChevronRight />}
                    Advanced Settings
                </button>
                {showAdvanced && (
                    <div className="settings-advanced">
                        <Field label="Model Path (override)" htmlFor={`${fieldId}-llamacpp-model-path`}>
                            <p className="field-help">Auto-filled when you download a model. Override to use a different GGUF file.</p>
                            <input
                                id={`${fieldId}-llamacpp-model-path`}
                                type="text"
                                className="input input-wide"
                                value={form.llamacpp_model_path}
                                onChange={(e) => update({ llamacpp_model_path: e.target.value })}
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
                                    value={form.llamacpp_gpu_layers}
                                    onChange={(e) => onInteger(e.target.value, (n) => update({ llamacpp_gpu_layers: n }))}
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
                                    value={form.llamacpp_ctx_size}
                                    onChange={(e) => onInteger(e.target.value, (n) => update({ llamacpp_ctx_size: n }))}
                                />
                            </Field>
                        </div>
                        <Field label="Server URL" htmlFor={`${fieldId}-llamacpp-url`}>
                            <input
                                id={`${fieldId}-llamacpp-url`}
                                type="text"
                                className="input input-medium"
                                value={form.llamacpp_base_url}
                                onChange={(e) => update({ llamacpp_base_url: e.target.value })}
                                placeholder="http://localhost:8080"
                            />
                        </Field>
                        <Field label="Binary Path" htmlFor={`${fieldId}-llamacpp-binary`}>
                            <p className="field-help">Path to the llama-server binary. Default assumes it is on PATH.</p>
                            <input
                                id={`${fieldId}-llamacpp-binary`}
                                type="text"
                                className="input input-wide"
                                value={form.llamacpp_binary_path}
                                onChange={(e) => update({ llamacpp_binary_path: e.target.value })}
                                placeholder="llama-server"
                            />
                        </Field>
                        <Field label="Display Name" htmlFor={`${fieldId}-llamacpp-display-name`}>
                            <p className="field-help">Label shown in the UI during translation. Auto-filled from tier selection.</p>
                            <input
                                id={`${fieldId}-llamacpp-display-name`}
                                type="text"
                                className="input input-medium"
                                value={form.llamacpp_model}
                                onChange={(e) => update({ llamacpp_model: e.target.value })}
                                placeholder="e.g. Qwen2.5-14B-Instruct"
                            />
                        </Field>
                    </div>
                )}
            </div>
        </Panel>
    )
}

export default LlamacppPanel
