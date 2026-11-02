import React, { useId } from "react"
import { useQuery } from "@tanstack/react-query"
import { API_BASE, fetchJson } from "@/lib/api"
import { listGames } from "@/games/registry"
import ErrorState from "@/components/ui/ErrorState"
import Banner from "@/components/ui/Banner"
import LoadingState from "@/components/ui/LoadingState"
import PageHeader from "@/components/ui/PageHeader"
import Panel from "@/components/ui/Panel"
import ApiKeysPanel from "@/pages/Settings/ApiKeysPanel"
import IgnoredModsPanel from "@/pages/Settings/IgnoredModsPanel"
import LlamacppPanel from "@/pages/Settings/LlamacppPanel"
import OllamaPanel from "@/pages/Settings/OllamaPanel"
import SystemPromptPreview from "@/pages/Settings/SystemPromptPreview"
import { PROVIDERS } from "@/pages/Settings/constants"
import { useLlamacpp } from "@/pages/Settings/useLlamacpp"
import { useOllama } from "@/pages/Settings/useOllama"
import { useSettingsForm } from "@/pages/Settings/useSettingsForm"
import "@/pages/Settings/styles.css"

/** One entry of the `/api/models/<provider>` list, with prices in dollars per million tokens. */
interface ModelOption {
    id: string
    label: string
    input_per_mtok: number
    output_per_mtok: number
}

/**
 * Load a provider's model list for the Model dropdown.
 *
 * @param provider `claude` or `openai`.
 * @returns The query for that list.
 */
function useModelList(provider: "claude" | "openai") {
    return useQuery({ queryKey: ["models", provider], queryFn: () => fetchJson<{ models: ModelOption[] }>(`${API_BASE}/models/${provider}`).then((body) => body.models) })
}

/**
 * Settings page for the translation provider, API keys, and batch size. Changes persist to the backend `.env` and apply without a restart.
 *
 * @returns The settings page, its loading state, or an error with Retry.
 */
const SettingsPage: React.FC = () => {
    // Prefixes every field id so each label can point at its control.
    const fieldId = useId()
    const settings = useSettingsForm()
    const ollama = useOllama(settings)
    const llamacpp = useLlamacpp(settings)
    const claudeModels = useModelList("claude")
    const openaiModels = useModelList("openai")
    const { form, update } = settings

    /** Reload the settings, and the model lists so a backend that was down fills the Model dropdown. */
    const retryLoad = () => {
        settings.reload()
        claudeModels.refetch()
        openaiModels.refetch()
    }

    if (settings.loading) return <LoadingState message="Loading settings..." />
    if (settings.loadError) {
        return (
            <ErrorState
                title="Could not load settings"
                message={`${settings.loadError}. Nothing has been changed. Check that the backend is running, then retry.`}
                action={{ label: "Retry", onClick: retryLoad }}
            />
        )
    }

    const provider = form.provider
    const isClaude = provider === "claude"
    const models = (isClaude ? claudeModels.data : openaiModels.data) ?? []

    return (
        <div className="settings-view">
            <PageHeader title="Settings" meta={<p>API Keys and Provider Configuration</p>} />

            <SystemPromptPreview fieldId={fieldId} />

            <Panel className="settings-panel" title="Translation Provider">
                <div className="provider-cards">
                    {PROVIDERS.map((p) => (
                        <div key={p.id} className={`provider-card ${provider === p.id ? "active" : ""}`} onClick={() => update({ provider: p.id })}>
                            <div className="provider-card-title">{p.label}</div>
                            <div className="provider-card-description">{p.description}</div>
                        </div>
                    ))}
                </div>
            </Panel>

            {(isClaude || provider === "openai") && (
                <Panel className="settings-panel" title="Model">
                    <select
                        value={isClaude ? form.claude_model : form.openai_model}
                        onChange={(e) => update(isClaude ? { claude_model: e.target.value } : { openai_model: e.target.value })}
                        aria-label="Model"
                        className="select"
                    >
                        {models.map((m) => (
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

            {provider === "ollama" && <OllamaPanel ollama={ollama} form={form} update={update} fieldId={fieldId} />}

            {provider === "llamacpp" && <LlamacppPanel llamacpp={llamacpp} form={form} update={update} fieldId={fieldId} />}

            {provider !== "manual" && provider !== "ollama" && provider !== "llamacpp" && (
                <ApiKeysPanel
                    provider={provider}
                    values={{ anthropic: form.anthropic_api_key, openai: form.openai_api_key, deepl: form.deepl_api_key }}
                    status={settings.keyStatus}
                    onChange={(field, value) => update({ [`${field}_api_key`]: value })}
                    fieldId={fieldId}
                />
            )}

            <Panel className="settings-panel" title="Batch Size" help="Number of strings sent per API request. Larger batches are more cost-efficient but may hit token limits.">
                <input
                    type="number"
                    min={1}
                    max={500}
                    aria-label="Batch size"
                    className="input input-number"
                    value={form.batch_size}
                    onChange={(e) => {
                        const val = parseInt(e.target.value, 10)
                        if (!isNaN(val)) update({ batch_size: val })
                    }}
                />
            </Panel>

            <IgnoredModsPanel mods={form.ignored_mods} onChange={(mods) => update({ ignored_mods: mods })} />

            {listGames().map((game) => {
                const slot = game.settingsPanel
                if (!slot) return null
                const values = Object.fromEntries(slot.keys.map((key) => [key, form.game[key] ?? ""]))
                return (
                    <slot.Panel
                        key={game.id}
                        values={values}
                        onChange={(key, value) => update({ game: { [key]: value } })}
                        onSaved={(key, value) => settings.markSaved({ game: { [key]: value } })}
                        fieldId={fieldId}
                    />
                )
            })}

            {settings.saveError && (
                <Banner tone="error" onDismiss={settings.dismissSaveError}>
                    {settings.saveError}
                </Banner>
            )}
            <div className="settings-save-row">
                <button className="btn btn-primary" disabled={!settings.isChanged || settings.saving} onClick={settings.save}>
                    {settings.saving ? "Saving..." : "Save Settings"}
                </button>
                {settings.saveSuccess && <span className="text-success">Settings saved successfully</span>}
            </div>
        </div>
    )
}

export default SettingsPage
