import React, { useState } from "react"
import { FaCheck, FaChevronDown, FaChevronRight, FaDownload, FaExclamationTriangle, FaPlay, FaStop } from "react-icons/fa"
import DownloadProgress from "@/components/ui/DownloadProgress"
import Field from "@/components/ui/Field"
import Panel from "@/components/ui/Panel"
import { VRAM_TIERS } from "@/pages/Settings/constants"
import type { OllamaState } from "@/pages/Settings/useOllama"
import type { SettingsForm } from "@/pages/Settings/useSettingsForm"

/** Props for OllamaPanel. */
interface OllamaPanelProps {
    ollama: OllamaState
    form: SettingsForm
    update: (patch: Partial<SettingsForm>) => void
    /** Prefix for field ids, unique to the Settings page. */
    fieldId: string
}

/**
 * Settings panel for the Ollama provider: server status and controls, the VRAM tier picker, model download, and the advanced fields.
 *
 * @param props The Ollama state, the Settings form and its update, and the field id prefix.
 * @returns The Ollama configuration panel.
 */
const OllamaPanel: React.FC<OllamaPanelProps> = ({ ollama, form, update, fieldId }) => {
    const [showAdvanced, setShowAdvanced] = useState(false)
    const { status, models, managed } = ollama
    const model = form.ollama_model
    const tierDefault = VRAM_TIERS.find((t) => t.tier === form.ollama_vram_tier)?.model || ""

    const isModelDownloaded = models.some((m) => m === model || m === model + ":latest" || m + ":latest" === model)
    // The user overrode the model when it differs from the VRAM tier default.
    const isModelOverride = model !== "" && model !== tierDefault
    const overrideModels = models.filter((m) => !VRAM_TIERS.some((t) => t.model === m))
    const tone = status === "running" ? "success" : status === "stopped" ? "warning" : status === "unknown" ? "dim" : "danger"
    const statusLabel = status === "running" ? "Running" : status === "stopped" ? "Stopped (not running)" : status === "unknown" ? "Checking..." : "Not Installed"

    /**
     * Pick a VRAM tier and its recommended model, or clear both when the tier is already picked.
     *
     * @param tier The tier clicked.
     */
    const selectTier = (tier: (typeof VRAM_TIERS)[number]) => {
        if (form.ollama_vram_tier === tier.tier) update({ ollama_vram_tier: "", ollama_model: "" })
        else update({ ollama_vram_tier: tier.tier, ollama_model: tier.model })
    }

    return (
        <Panel className="settings-panel" title="Ollama Configuration">
            <div className="status-row">
                <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />
                <span className="status-label">{statusLabel}</span>
                {status === "stopped" && (
                    <button className="btn btn-primary btn-sm status-action" disabled={ollama.starting} onClick={ollama.start}>
                        <FaPlay />
                        {ollama.starting ? "Starting..." : "Start"}
                    </button>
                )}
                {status === "running" && managed && (
                    <button className="btn btn-danger btn-sm status-action" disabled={ollama.stopping} onClick={ollama.stop}>
                        <FaStop />
                        {ollama.stopping ? "Stopping..." : "Stop"}
                    </button>
                )}
                {status === "running" && !managed && <span className="note status-action">Started externally</span>}
            </div>

            {status === "not_installed" && (
                <div className="settings-block">
                    <p className="settings-block-help">Ollama is not installed. Click below to download and install it automatically.</p>
                    <button className="btn btn-primary" disabled={ollama.installing} onClick={ollama.install}>
                        <FaDownload />
                        {ollama.installing ? "Downloading installer..." : "Install Ollama"}
                    </button>
                </div>
            )}

            <div className="settings-block">
                <h4 className="settings-subheading">GPU VRAM Tier</h4>
                <p className="settings-block-help">Select your GPU's VRAM to get the best model recommendation for translation quality.</p>
                <div className="vram-tier-cards">
                    {VRAM_TIERS.map((t) => (
                        <div key={t.tier} className={`vram-tier-card ${form.ollama_vram_tier === t.tier ? "active" : ""}`} onClick={() => selectTier(t)}>
                            <div className="tier-card-title">{t.label}</div>
                            <div className="tier-card-model">{t.model}</div>
                            <div className="tier-card-meta">{t.description}</div>
                            <div className="tier-card-meta">{t.size} download</div>
                        </div>
                    ))}
                </div>
            </div>

            {form.ollama_vram_tier && (
                <div className="settings-block">
                    <div className="settings-selected-row">
                        <span className="settings-selected-label">
                            Selected model: <strong className="accent-text">{model}</strong>
                        </span>
                        {status === "running" && (
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

                    {status === "running" && !isModelDownloaded && !ollama.pulling && (
                        <button className="btn btn-primary" onClick={() => ollama.pull(model)}>
                            <FaDownload />
                            Download Model
                        </button>
                    )}

                    {ollama.pulling && ollama.pullProgress && (
                        <div className="settings-subrow">
                            <div className="progress-status">{ollama.pullProgress.status}...</div>
                            {(ollama.pullProgress.total ?? 0) > 0 && <DownloadProgress completed={ollama.pullProgress.completed || 0} total={ollama.pullProgress.total ?? 0} />}
                        </div>
                    )}
                    {ollama.pulling && !ollama.pullProgress && <div className="progress-status">Starting download...</div>}
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
                        <Field label="Ollama URL" htmlFor={`${fieldId}-ollama-url`}>
                            <input
                                id={`${fieldId}-ollama-url`}
                                type="text"
                                className="input input-medium"
                                value={form.ollama_base_url}
                                onChange={(e) => update({ ollama_base_url: e.target.value })}
                                placeholder="http://localhost:11434"
                            />
                        </Field>
                        <Field label="Model (override)" htmlFor={`${fieldId}-ollama-override`}>
                            <p className="field-help">Use an installed model instead of the recommended one above.</p>
                            {overrideModels.length > 0 ? (
                                <select
                                    id={`${fieldId}-ollama-override`}
                                    value={isModelOverride ? model : ""}
                                    className="select input-medium"
                                    onChange={(e) => update({ ollama_model: e.target.value || tierDefault })}
                                >
                                    <option value="">None (use recommended)</option>
                                    {overrideModels.map((m) => (
                                        <option key={m} value={m}>
                                            {m}
                                        </option>
                                    ))}
                                </select>
                            ) : (
                                <span className="note">{status === "running" ? "No other models installed" : "Ollama not running"}</span>
                            )}
                        </Field>
                    </div>
                )}
            </div>
        </Panel>
    )
}

export default OllamaPanel
