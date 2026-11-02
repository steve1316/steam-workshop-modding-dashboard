import React, { useState } from "react"
import { gameApi } from "@/lib/api"
import { useActiveGame } from "@/context/ActiveGameContext"
import Panel from "@/components/ui/Panel"

/** Props for SystemPromptPreview. */
interface SystemPromptPreviewProps {
    /** Prefix for field ids, unique to the Settings page. */
    fieldId: string
}

/**
 * Settings panel that loads the system prompt the active game sends for a chosen source language.
 *
 * @param props The field id prefix.
 * @returns The prompt preview panel.
 */
const SystemPromptPreview: React.FC<SystemPromptPreviewProps> = ({ fieldId }) => {
    // The preview loads from the game shown in the sidebar.
    const game = useActiveGame()
    const [systemPrompt, setSystemPrompt] = useState("")
    const [sourceLang, setSourceLang] = useState("Chinese")
    const [loading, setLoading] = useState(false)

    /** Load the prompt, or close it when one is already shown. */
    const toggle = async () => {
        if (systemPrompt) {
            setSystemPrompt("")
            return
        }
        setLoading(true)
        try {
            const res = await gameApi(game.id).get(`/translate/system-prompt?source_lang=${encodeURIComponent(sourceLang)}`)
            const data = await res.json()
            setSystemPrompt(data.system_prompt || "")
        } catch (err) {
            console.error("Failed to fetch system prompt:", err)
            setSystemPrompt("Error fetching system prompt.")
        } finally {
            setLoading(false)
        }
    }

    return (
        <Panel
            className="settings-panel"
            title="System Prompt Preview"
            help={`View the system prompt sent for ${game.displayName} translations. Uses that game's base glossary and translation settings.`}
        >
            <div className="settings-inline-row">
                <label className="field-label" htmlFor={`${fieldId}-prompt-lang`}>
                    Source Language
                </label>
                <select id={`${fieldId}-prompt-lang`} value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} className="select select-auto">
                    <option value="Chinese">Chinese</option>
                    <option value="Korean">Korean</option>
                    <option value="Japanese">Japanese</option>
                </select>
                <button className="btn btn-outline" onClick={toggle} disabled={loading}>
                    {loading ? "Loading..." : systemPrompt ? "Unload Prompt" : "Load Prompt"}
                </button>
            </div>
            {systemPrompt && <pre className="code-block">{systemPrompt}</pre>}
        </Panel>
    )
}

export default SystemPromptPreview
