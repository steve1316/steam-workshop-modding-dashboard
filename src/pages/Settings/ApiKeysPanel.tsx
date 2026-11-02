import React, { useState } from "react"
import { FaCheck, FaEye, FaEyeSlash, FaExclamationTriangle } from "react-icons/fa"
import Panel from "@/components/ui/Panel"
import { PROVIDERS, type KeyField } from "@/pages/Settings/constants"

/** Props for ApiKeysPanel. */
interface ApiKeysPanelProps {
    /** The selected provider id, whose key row is highlighted. */
    provider: string
    /** Keys typed but not saved yet. Blank means no change. */
    values: Record<KeyField, string>
    /** The backend's masked form of each saved key, blank when none is set. */
    status: Record<KeyField, string>
    onChange: (field: KeyField, value: string) => void
    /** Prefix for field ids, unique to the Settings page. */
    fieldId: string
}

/**
 * Settings panel with a masked input for each provider's API key.
 *
 * @param props The selected provider, typed keys, saved key status, change handler, and field id prefix.
 * @returns The API keys panel.
 */
const ApiKeysPanel: React.FC<ApiKeysPanelProps> = ({ provider, values, status, onChange, fieldId }) => {
    const [visible, setVisible] = useState<Record<KeyField, boolean>>({ anthropic: false, openai: false, deepl: false })

    return (
        <Panel className="settings-panel" title="API Keys">
            {PROVIDERS.map((p) => {
                const field = p.keyField
                if (!field) return null
                const isConfigured = status[field] !== ""
                return (
                    <div key={field} className={`key-row${provider === p.id ? " selected" : ""}`}>
                        <div className="key-row-header">
                            <label className="field-label" htmlFor={`${fieldId}-key-${field}`}>
                                {p.label} API Key
                            </label>
                            <span className={`key-status ${isConfigured ? "configured" : "missing"}`}>
                                {isConfigured ? (
                                    <>
                                        <FaCheck /> {status[field]}
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
                                type={visible[field] ? "text" : "password"}
                                value={values[field]}
                                onChange={(e) => onChange(field, e.target.value)}
                                placeholder={isConfigured ? "Enter new key to update..." : "Enter API key..."}
                            />
                            <button className="key-toggle-btn" onClick={() => setVisible((prev) => ({ ...prev, [field]: !prev[field] }))} title={visible[field] ? "Hide" : "Show"} type="button">
                                {visible[field] ? <FaEyeSlash /> : <FaEye />}
                            </button>
                        </div>
                    </div>
                )
            })}
        </Panel>
    )
}

export default ApiKeysPanel
